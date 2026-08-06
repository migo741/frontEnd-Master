from __future__ import annotations

import unittest

from solution import Chunk, Claim, HybridIndex, validate_citations


class RagTest(unittest.TestCase):
    def setUp(self) -> None:
        self.index = HybridIndex()
        self.index.upsert([
            Chunk("c1", "d1", "t1", 1, "退款", "退款期限为七天，需要订单号。", frozenset({"support"})),
            Chunk("c2", "d2", "t1", 1, "登录", "重置密码需要验证邮箱。", frozenset()),
            Chunk("c3", "d3", "t2", 1, "私有", "租户二的退款密钥。", frozenset()),
            Chunk("c4", "d4", "t1", 1, "财务", "内部退款上限。", frozenset({"finance"})),
        ])

    def test_acl_before_ranking(self) -> None:
        hits = self.index.search("退款", tenant_id="t1", roles=frozenset({"support"}))
        self.assertEqual([h.chunk.chunk_id for h in hits], ["c1"])
        self.assertNotIn("c3", [h.chunk.chunk_id for h in hits])
        self.assertNotIn("c4", [h.chunk.chunk_id for h in hits])

    def test_citation_validation(self) -> None:
        hits = self.index.search("退款期限", tenant_id="t1", roles=frozenset({"support"}))
        validate_citations([Claim("退款期限七天", ("c1",))], hits)
        with self.assertRaises(ValueError):
            validate_citations([Claim("退款期限七天", ("missing",))], hits)
        with self.assertRaises(ValueError):
            validate_citations([Claim("火星天气", ("c1",))], hits)

    def test_delete_propagates_to_index(self) -> None:
        self.index.delete_document("t1", "d1")
        self.assertEqual(self.index.search("退款", tenant_id="t1", roles=frozenset({"support"})), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

