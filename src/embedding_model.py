"""Contrato unico do GTE para documentos e consultas; imports pesados sob demanda."""
from src.database.embeddings import validate_vector

MODEL = 'Alibaba-NLP/gte-multilingual-base'
REVISION = '9bbca17d9273fd0d03d5725c7a4b0f6b45142062'
CODE_REVISION = '40ced75c3017eb27626c9d4ea981bde21a2662f4'
MAX_TOKENS = 8192


def load_model(device='cpu', threads=8):
    if device not in ('cpu', 'cuda') or not 1 <= threads <= 16:
        raise ValueError('dispositivo_ou_threads_invalido')
    import torch
    torch.set_num_threads(threads)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('cuda_indisponivel')
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL, revision=REVISION, trust_remote_code=True,
        device=device, model_kwargs={'code_revision': CODE_REVISION},
        config_kwargs={'code_revision': CODE_REVISION})
    if model.max_seq_length != MAX_TOKENS:
        raise ValueError('janela inesperada do GTE')
    model.float().eval()
    return model


def encode_checked(model, texts, *, batch_size=2):
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError('texto vazio ou invalido')
    if model.max_seq_length != MAX_TOKENS:
        raise ValueError('janela inesperada do GTE')
    lengths = model.tokenizer(texts, add_special_tokens=True, truncation=False,
        padding=False, return_attention_mask=False, return_length=True)['length']
    if len(lengths) != len(texts) or any(n > MAX_TOKENS for n in lengths):
        raise ValueError('entrada excede janela; proibido truncar')
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                           show_progress_bar=False)
    if len(vectors) != len(texts):
        raise ValueError('quantidade de vetores invalida')
    return [validate_vector(vector) for vector in vectors], list(map(int, lengths))
