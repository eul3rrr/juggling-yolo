"""LosslessCut CSV parsing and source-video/segment pairing."""
from dataclasses import dataclass, asdict
import csv
import math
from pathlib import Path

@dataclass(frozen=True)
class Segment:
    index: int
    start: float
    end: float
    label: str = ''
    source: str = ''

    def as_dict(self):
        return asdict(self)

def _number(value, field, row):
    try:
        value = float(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f'Invalid LosslessCut {field} at row {row}: {value!r}')
    if not math.isfinite(value):
        raise ValueError(f'Non-finite LosslessCut {field} at row {row}')
    return value

def parse_losslesscut_csv(path, duration=None):
    """Parse normal LosslessCut Start,End,Name CSV output.

    Incomplete trailing rows (empty or ``undefined`` end) are ignored; any
    other malformed row is rejected. Times are seconds and ranges are half-open.
    """
    path = Path(path)
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fields = {str(x).strip().lower() for x in (reader.fieldnames or [])}
        if not {'start', 'end'} <= fields:
            raise ValueError('LosslessCut CSV must contain Start and End columns')
        result = []
        for rownum, raw in enumerate(reader, 2):
            row = {str(k).strip().lower(): (v or '').strip() for k, v in raw.items() if k is not None}
            start_raw, end_raw = row.get('start', ''), row.get('end', '')
            if not start_raw and not end_raw:
                continue
            if end_raw.lower() in ('undefined', 'nan', 'none', ''):
                continue
            start, end = _number(start_raw, 'start', rownum), _number(end_raw, 'end', rownum)
            if start < 0 or end <= start:
                raise ValueError(f'Invalid LosslessCut range at row {rownum}: {start}, {end}')
            if duration is not None:
                if duration <= 0 or not math.isfinite(duration):
                    raise ValueError('Invalid video duration')
                if start >= duration:
                    continue
                end = min(end, duration)
                if end <= start:
                    continue
            result.append(Segment(len(result), start, end, row.get('name', ''), str(path.resolve())))
    if not result:
        raise ValueError(f'No usable LosslessCut segments in {path}')
    return result

def pair_video_segments(video, segments=None):
    video = Path(video)
    csv_path = Path(segments) if segments else Path(str(video) + '.csv')
    if not video.is_file():
        raise FileNotFoundError(f'Video not found: {video}')
    if not csv_path.is_file():
        raise FileNotFoundError(f'LosslessCut CSV not found: {csv_path}')
    return video, csv_path

def discover_pairs(source_dir):
    root = Path(source_dir).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f'Source directory not found: {root}')
    pairs = []
    for video in sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {'.mp4', '.mov', '.mkv', '.avi', '.webm'}):
        csv_path = Path(str(video) + '.csv')
        if csv_path.is_file():
            pairs.append((video, csv_path))
    return pairs

def segment_for_frame(frame, fps, segments):
    timestamp = frame / fps
    return next((s for s in segments if s.start <= timestamp < s.end), None)

def segment_frame_bounds(segment, fps, count):
    return max(0, math.ceil(segment.start * fps)), min(count, math.ceil(segment.end * fps))
