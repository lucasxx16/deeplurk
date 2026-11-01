"""Check frozen mapping and adapter mechanics without model weights or network."""
import hashlib
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from calibration_adapter import adapt_context, prepare
from score import rino_probs

HERE = Path(__file__).resolve().parent


class FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(map(ord, text))
    def decode(self, ids, skip_special_tokens=False):
        return ''.join(map(chr, ids))
    def apply_chat_template(self, messages, tokenize, add_generation_prompt=False):
        text = ''.join(m['role'] + ':' + m['content'] for m in messages)
        return self.encode(text) if tokenize else text


class OfflineTests(unittest.TestCase):
    def test_frozen_mapping(self):
        data = (HERE / 'rino-fit-frozen.json').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), '9a7e0df7c709c4c75477ad6fe5101225a880231c4759410211d4f96efce6fea2')
        fit = json.loads(data)['fit']['model']
        p = rino_probs([0., 1., 2.], fit)
        self.assertTrue(((p >= 0) & (p <= 1)).all())
        self.assertTrue(all(abs(float(x) - 1) < 1e-10 for x in p.sum(axis=1)))
        self.assertLess(float(p[0] @ [1, 2, 3, 4, 5]), float(p[2] @ [1, 2, 3, 4, 5]))

    def test_adapter_preserves_hypothesis(self):
        with patch('calibration_adapter.prompt_constants', return_value={'CRITERIA_DEFINITIONS': {}, 'USER_PROMPT_TEMPLATE': '{context}'}):
            messages, ids, report = prepare(FakeTokenizer(), 'candidate', 'context', 'hypothesis')
            self.assertEqual(messages[1]['content'], 'hypothesis')
            self.assertTrue(report['full_hypothesis_preserved'])
            self.assertEqual(len(ids), report['total_tokens'])

    def test_long_unstructured_context_fails_closed(self):
        with self.assertRaises(ValueError):
            adapt_context(FakeTokenizer(), 'candidate', 'x' * 2050)


if __name__ == '__main__':
    unittest.main()
