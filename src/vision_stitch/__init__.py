"""Vision-LLM tracklet stitching judge (evidence, judging, human review).

Isolated evaluation tooling: it reads existing tracklet CSVs and video frames,
asks a vision model to decide END -> successor stitches, and serves a local
review UI so a human can label whether each proposed stitch is correct.

It never modifies the detector, Norfair, the stitcher, or any identity layer.
"""
