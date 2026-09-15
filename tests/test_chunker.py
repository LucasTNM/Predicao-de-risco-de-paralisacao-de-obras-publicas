"""Invariantes de cobertura com o tokenizer BERTimbau real e fixado."""
import unittest

from src.parsers.chunker import SlidingWindow, load_chunker


class TestChunker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunker = load_chunker()

    def test_boundaries_and_coverage(self):
        for size in (0, 1, 449, 450, 451, 850, 851, 1250):
            with self.subTest(tokens=size):
                text = 'obra ' * size
                chunks = self.chunker.chunks(text)
                ids = self.chunker.tokenizer(text, add_special_tokens=False)['input_ids']
                if size == 0:
                    self.assertEqual(chunks, [])
                    continue
                covered = []
                for i, c in enumerate(chunks):
                    self.assertEqual(c.position, i)
                    self.assertEqual(c.text, text[c.char_start:c.char_end])
                    self.assertEqual(list(c.token_ids), ids[c.token_start:c.token_end])
                    self.assertLessEqual(len(c.token_ids) + 2, 512)
                    covered.extend(c.token_ids if i == 0 else c.token_ids[self.chunker.overlap:])
                    if i:
                        self.assertEqual(chunks[i-1].token_ids[-50:], c.token_ids[:50])
                self.assertEqual(covered, ids)
                self.assertEqual(chunks[-1].token_end, len(ids))

    def test_offsets_preserve_accents_values_and_subtokens(self):
        text = ('Referência nº 27: R$ 1.234,56 — fiscalização intermunicipalíssima.\n\n' * 120)
        chunks = self.chunker.chunks(text)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertEqual(c.text, text[c.char_start:c.char_end])
            self.assertEqual(c.token_end-c.token_start, len(c.token_ids))

    def test_invalid_parameters(self):
        for size, overlap in ((0, 0), (450, -1), (450, 450), (511, 50), (450, 451)):
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                SlidingWindow(self.chunker.tokenizer, size, overlap)

    def test_no_overlap_and_whitespace(self):
        chunker = SlidingWindow(self.chunker.tokenizer, 7, 0)
        self.assertEqual(chunker.chunks(' \n\t'), [])
        chunks = chunker.chunks('obra ' * 21)
        self.assertEqual([len(c.token_ids) for c in chunks], [7, 7, 7])
        self.assertNotEqual(chunker.config, self.chunker.config)
