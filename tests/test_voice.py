import unittest
from unittest.mock import patch

import voice


class VoiceInteractionTests(unittest.TestCase):
    def test_duplicate_playback_is_rejected_without_queueing(self):
        acquired = voice._speaking_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            with patch.object(voice, "_is_enabled", return_value=True):
                self.assertFalse(voice.speak("A duplicate response"))
        finally:
            voice._speaking_lock.release()

    def test_stop_signal_makes_local_playback_report_interruption(self):
        class FakeEngine:
            def say(self, text):
                self.text = text

            def runAndWait(self):
                voice._stop_requested.set()

        with patch.object(voice, "_is_enabled", return_value=True), patch.object(
            voice, "_speak_with_powershell", return_value=False
        ), patch.object(voice, "_get_engine", return_value=FakeEngine()), patch.object(
            voice, "_setting", return_value=""
        ):
            self.assertFalse(voice.speak("Exact response, sir."))

    def test_clean_text_preserves_the_response_content_for_tts(self):
        self.assertEqual(
            voice._clean_text("The result is **ready**: https://example.test now."),
            "The result is ready: now.",
        )


if __name__ == "__main__":
    unittest.main()
