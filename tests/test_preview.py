import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import app


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "图.jpg"
        Image.new("RGB", (1920, 1080), "navy").save(self.path)

    def shot(self, i=1):
        return dict(shot_no=i, start_tc="00:00:01", end_tc="00:00:02", duration=1,
                    keyframe=str(self.path), motion_image=str(self.path))

    def test_empty_busy_and_duplicate_never_clear(self):
        self.assertTrue(all(value == app.gr.skip() for value in app._show(1, "关键帧", [])))
        browser = app._to_browser([self.shot()], "run")
        payload, shown = app._show(1, "关键帧", browser)
        self.assertEqual(json.loads(payload)["no"], 1)
        self.assertEqual(app._show(1, "关键帧", browser, shown), (app.gr.skip(), app.gr.skip()))
        self.assertEqual(app._show(1, "运动图", browser, shown, True), (app.gr.skip(), app.gr.skip()))

    def test_missing_preview_is_nonfatal(self):
        shot = app._to_browser([self.shot()], "run")[0]
        shot["keyframe"] = "missing.jpg"
        self.assertIn("error", json.loads(app.preview_payload(shot)))

    def test_programmatic_slider_has_no_change_listener(self):
        deps = app.demo.config["dependencies"]
        slider_id = app.shot_slider._id
        self.assertEqual([event for d in deps for cid, event in d["targets"] if cid == slider_id], ["input"])
        main = next(d for d in deps if d["targets"] == [(app.btn._id, "click")])
        self.assertEqual(main["show_progress_on"], [app.progress_area._id])
        for d in deps:
            if app.viewer._id in d["outputs"] and d is not main:
                self.assertEqual(d["show_progress"], "hidden")

    def test_fast_stream_is_bounded_and_finishes_last(self):
        clock = [0.0]
        shots = [self.shot(i) for i in range(1, 101)]

        def pipeline(*args, **kwargs):
            for i, shot in enumerate(shots, 1):
                clock[0] += .04
                yield "shot", i, len(shots), shot, .5 + .45 * i / len(shots)
            yield "done", dict(shots=shots, fps=24, out_dir=self.temp.name,
                               files=dict(html="x.html", csv="x.csv", md="x.md"))

        with patch.object(app, "run_pipeline", pipeline), patch.object(app.time, "monotonic", lambda: clock[0]):
            updates = [dict(zip(app.OUTPUT_NAMES, row)) for row in app.process_video(str(self.path), None, 27, "快速")]
        previews = [json.loads(u["viewer"]) for u in updates if isinstance(u["viewer"], str) and '"src"' in u["viewer"]]
        self.assertLessEqual(len(previews), 7)
        self.assertEqual(previews[-1]["no"], 100)
        final = updates[-1]
        self.assertEqual(final["shot_slider"]["value"], 100)
        self.assertEqual(len(final["gallery"]), 100)
        self.assertEqual(len(final["browser_state"]), 100)
        self.assertFalse(final["busy_state"])
        galleries = [u["gallery"] for u in updates if isinstance(u["gallery"], list)]
        self.assertLessEqual(len(galleries), 5)
        self.assertEqual(len(galleries[1]), 1)  # snapshots must not mutate after yield

    def test_exception_unlocks_retry_without_clearing_viewer(self):
        with patch.object(app, "run_pipeline", side_effect=RuntimeError("test error")):
            rows = list(app.process_video(str(self.path), None, 27, "快速"))
        final = dict(zip(app.OUTPUT_NAMES, rows[-1]))
        self.assertEqual(final["viewer"], app.gr.skip())
        self.assertFalse(final["busy_state"])
        self.assertTrue(final["btn"]["interactive"])

    def test_gallery_index_handles_a_missing_frame(self):
        shots = [self.shot(i) for i in range(1, 4)]
        shots[0]["keyframe"] = ""
        browser = app._to_browser(shots, "run")
        event = app.gr.SelectData(None, {"index": 0, "value": None})
        payload, slider, _ = app._on_gallery(event, "关键帧", browser, None, False)
        self.assertEqual(slider["value"], 2)
        self.assertEqual(json.loads(payload)["no"], 2)


if __name__ == "__main__":
    unittest.main()
