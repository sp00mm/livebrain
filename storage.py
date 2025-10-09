import os
import sys
import json
import libsql

class DocumentStorage:
    @staticmethod
    def get_db_path():
        if sys.platform == 'darwin':
            app_support = os.path.expanduser("~/Library/Application Support/LiveBrain")
        else:
            app_support = os.path.expanduser("~/.livebrain")
        
        os.makedirs(app_support, exist_ok=True)
        return os.path.join(app_support, "livebrain.db")
    
    def __init__(self):
        db_path = f"file:{self.get_db_path()}"
        self.conn = libsql.connect(db_path)
        
    def initialize(self, dimension):
        self.conn.execute("drop table if exists documents")
        self.conn.execute(f"""
            create table documents (
                id integer primary key autoincrement,
                filepath text not null,
                text text not null,
                embedding f32_blob({dimension})
            )
        """)
        self.conn.execute("create index documents_idx on documents(libsql_vector_idx(embedding))")
        self.conn.commit()
    
    def insert(self, filepath, text, embedding):
        embedding_json = json.dumps(embedding)
        self.conn.execute(
            "insert into documents (filepath, text, embedding) values (?, ?, vector32(?))",
            [filepath, text[:1000], embedding_json]
        )
        self.conn.commit()
    
    def search(self, query_embedding, limit=10):
        embedding_json = json.dumps(query_embedding)
        cursor = self.conn.execute(f"""
            select d.filepath, d.text, vector_distance_cos(d.embedding, vector32(?)) as distance
            from vector_top_k('documents_idx', vector32(?), ?) as vtk
            join documents d on d.rowid = vtk.id
            order by distance asc
        """, [embedding_json, embedding_json, limit])
        
        results = cursor.fetchall()
        return [
            {
                'distance': 1 - row[2],
                'entity': {'filepath': row[0], 'text': row[1]}
            }
            for row in results
        ]
