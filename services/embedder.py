import os
import sys
import onnxruntime as ort
from tokenizers import Tokenizer
import numpy as np

class Embedder:
    @staticmethod
    def get_model_dir():
        if sys.platform == 'darwin':
            app_support = os.path.expanduser("~/Library/Application Support/Livebrain")
        else:
            app_support = os.path.expanduser("~/.livebrain")
        
        os.makedirs(app_support, exist_ok=True)
        return os.path.join(app_support, "models", "embeddinggemma-onnx")
    
    def __init__(self):
        model_dir = self.get_model_dir()
        model_path = os.path.join(model_dir, "onnx", "model_q4.onnx")
        tokenizer_path = os.path.join(model_dir, "tokenizer.json")
        self.session = ort.InferenceSession(model_path)
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_padding(pad_id=0, pad_token="<pad>")
        self.tokenizer.enable_truncation(max_length=2048)
        self.query_prefix = "task: search result | query: "
        self.doc_prefix = "title: none | text: "
    
    def embed(self, text, is_query=True):
        prefix = self.query_prefix if is_query else self.doc_prefix
        encoded = self.tokenizer.encode(prefix + text)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
        _, embedding = self.session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})
        return embedding[0].tolist()

