from __future__ import annotations

import ast

from helpers import IsolatedCase, SCRIPT

SCALARS = {
    'description: Plain one line': 'Plain one line',
    'description: "Quoted: with colon"': 'Quoted: with colon',
    "description: 'Single ''quoted'''": "Single 'quoted'",
    'description: >\n  Folded line one\n  line two': 'Folded line one line two',
    'description: >-\n  Folded strip\n  two': 'Folded strip two',
    'description: |\n  Literal one\n  two': 'Literal one\ntwo',
    'description: Plain start\n  continued here': 'Plain start continued here',
}
STEMS = {"debugging": "debug", "testing": "test", "tests": "test", "invoices": "invoic",
         "invoice": "invoic", "created": "creat", "create": "creat", "creating": "creat",
         "running": "run", "classes": "class", "class": "class", "databases": "databas",
         "database": "databas", "status": "status", "speed": "speed", "pages": "page",
         "page": "page", "policies": "policy", "calling": "call"}


class ParseTests(IsolatedCase):
    def test_scalar_styles(self):
        for case, expected in SCALARS.items():
            with self.subTest(case=case):
                meta, body = self.s.parse_frontmatter("---\nname: x\n" + case + "\n---\nBody")
                self.assertEqual(meta["description"], expected)
                self.assertEqual(body, "Body")

    def test_crlf_and_bom(self):
        self.assertEqual(self.s.parse_frontmatter("\ufeff---\r\nname: a\r\ndescription: D\r\n---\r\nBody"),
                         ({"name": "a", "description": "D"}, "Body"))

    def test_no_frontmatter(self):
        self.assertEqual(self.s.parse_frontmatter("Body"), ({}, "Body"))

    def test_unclosed_frontmatter(self):
        text = "---\nname: x\nBody"
        self.assertEqual(self.s.parse_frontmatter(text), ({}, text))

    def test_when_to_use_key_kept(self):
        self.assertEqual(self.s.parse_frontmatter("---\nWhen_To_Use: now\n---")[0]["when_to_use"], "now")

    def test_stem_table(self):
        for word, expected in STEMS.items():
            with self.subTest(word=word):
                self.assertEqual(self.s.stem(word), expected)

    def test_tokenize(self):
        self.assertEqual(self.s.tokenize("Use when DEBUGGING the failing-tests, ve hata_ayıklama!"),
                         ["debug", "fail", "test", "hata", "ayıklama"])

    def test_turkish_function_words_dropped(self):
        self.assertEqual(self.s.tokenize("bi skıntı var de da hangi"), ["skıntı"])

    def test_python38_syntax(self):
        ast.parse(SCRIPT.read_text(), feature_version=(3, 8))

    def test_turkish_dotted_capital_i(self):
        self.assertEqual(self.s.tokenize("İstanbul İzmir"), ["istanbul", "izmir"])
