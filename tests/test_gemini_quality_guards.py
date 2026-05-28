import unittest

from polytext.converter.gemini_quality_guards import tail_has_excessive_repetition


class TestGeminiQualityGuards(unittest.TestCase):
    def test_detects_consecutive_repeated_sentences_below_ratio_threshold(self):
        text = (
            "gli davamo nomi veri e falsi. "
            "_Elio_ all'anagrafe e io gli gli dicevo _Roberto Gustativi_. "
            "E questi scrivevano Roberto Gustativi. "
            "E la soddisfazione perversa era andare a comprare il giornale. "
            "È successo. "
            "Sono stato. "
            "Che è successo? "
            "Siamo passati dal basement. "
            "Siamo passati dal basement. "
            "Siamo passati dal basement. "
            "Siamo passati dal basement. "
            "Il miglior finale di sempre. "
            "Grazie, grazie, grazie, grazie, grazie, grazie, grazie. "
            "E vi grazie."
        )

        self.assertTrue(
            tail_has_excessive_repetition(text, tail_lines=200, threshold=0.35)
        )


if __name__ == "__main__":
    unittest.main()
