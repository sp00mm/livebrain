from dataclasses import dataclass, field
from typing import Callable
import json
import os

from models import FileReference, StepType


@dataclass
class ToolContext:
    folder_ids: list[str]
    embedder: object
    rag: object
    scanner: object
    folder_paths: list[str]


@dataclass
class ToolResult:
    output: str
    file_refs: list[FileReference] = field(default_factory=list)
    resource_ids: list[str] = field(default_factory=list)
    summary: str = ''
    details: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    handler: Callable[[dict, ToolContext], ToolResult]
    should_include: Callable[[ToolContext], bool]
    step_type: StepType


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def get_available(self, ctx: ToolContext) -> list[Tool]:
        return [t for t in self._tools.values() if t.should_include(ctx)]

    def build_schemas(self, ctx: ToolContext) -> list[dict]:
        schemas = [
            {'type': 'web_search'},
            {'type': 'code_interpreter', 'container': {'type': 'auto'}},
        ]
        for tool in self._tools.values():
            if tool.should_include(ctx):
                schemas.append(tool.schema)
        return schemas

REGISTRY = ToolRegistry()


SEARCH_FILES_SCHEMA = {
    'type': 'function',
    'name': 'search_files',
    'description': "Search through the user's files and folders. ALWAYS use this tool when the user's question could be answered or supported by their documents. Search proactively — don't ask the user what to search for.",
    'parameters': {
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': 'Natural language search query to find relevant content'
            }
        },
        'required': ['query'],
        'additionalProperties': False
    },
    'strict': True
}


def _handle_search_files(args: dict, ctx: ToolContext) -> ToolResult:
    embedding = ctx.embedder.embed(args['query'], is_query=True)
    results = ctx.rag.search(embedding, resource_ids=ctx.folder_ids, limit=10)
    context_parts = []
    file_refs = []
    used_resource_ids = []
    seen_paths = set()
    seen_resource_ids = set()
    for r in results:
        resource = r['resource']
        chunk = r['chunk']
        similarity = r['similarity']
        context_parts.append(json.dumps({
            'source': resource.name,
            'filepath': chunk.filepath,
            'text': chunk.text,
            'relevance': round(similarity, 3),
            'location': chunk.source_meta
        }))
        if chunk.filepath not in seen_paths:
            seen_paths.add(chunk.filepath)
            file_refs.append(FileReference(
                resource_id=resource.id,
                filepath=chunk.filepath,
                display_name=os.path.basename(chunk.filepath),
                relevance_score=similarity,
                source_meta=chunk.source_meta
            ))
        if resource.id not in seen_resource_ids:
            seen_resource_ids.add(resource.id)
            used_resource_ids.append(resource.id)

    matched_files = [ref.display_name for ref in file_refs]
    return ToolResult(
        output=f'[{",".join(context_parts)}]',
        file_refs=file_refs,
        resource_ids=used_resource_ids,
        summary=f'Searched: "{args["query"]}"',
        details=[('Found in', ', '.join(matched_files)), (f'{len(file_refs)} results', '')]
    )


REGISTRY.register(Tool(
    name='search_files',
    description='Search files: search through scanned folders for relevant content. Always search first, never ask what to look for.',
    schema=SEARCH_FILES_SCHEMA,
    handler=_handle_search_files,
    should_include=lambda ctx: bool(ctx.folder_ids),
    step_type=StepType.SEARCHING_FILES,
))


READ_FILE_SCHEMA = {
    'type': 'function',
    'name': 'read_file',
    'description': "Read the full contents of a specific file. Use this after searching to get more context from a file, or when the user asks about a specific file visible in the file tree.",
    'parameters': {
        'type': 'object',
        'properties': {
            'path': {
                'type': 'string',
                'description': 'Full file path to read'
            }
        },
        'required': ['path'],
        'additionalProperties': False
    },
    'strict': True
}


def _handle_read_file(args: dict, ctx: ToolContext) -> ToolResult:
    path = os.path.realpath(args['path'])
    allowed = any(
        path.startswith(os.path.realpath(fp))
        for fp in ctx.folder_paths
    )
    assert allowed, f'path outside allowed folders: {path}'

    text = ctx.scanner.extract_text(path) or ''
    if len(text) > 32000:
        text = text[:32000] + '\n\n[Truncated — file is too large to show in full]'

    ref = FileReference(
        filepath=path,
        display_name=os.path.basename(path),
    )
    return ToolResult(
        output=text,
        file_refs=[ref],
        resource_ids=[],
        summary=f'Read: {os.path.basename(path)}',
        details=[('File', os.path.basename(path))]
    )


REGISTRY.register(Tool(
    name='read_file',
    description='Read the full contents of a specific file',
    schema=READ_FILE_SCHEMA,
    handler=_handle_read_file,
    should_include=lambda ctx: bool(ctx.folder_ids),
    step_type=StepType.READING_FILE,
))
