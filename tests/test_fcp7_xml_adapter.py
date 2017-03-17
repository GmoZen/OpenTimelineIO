#!/usr/bin/env python2.7

"""Test final cut pro xml."""

# python
import os
import tempfile
import unittest
import collections
from xml.etree import cElementTree

import opentimelineio as otio

SAMPLE_DATA_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
FCP7_XML_EXAMPLE_PATH = os.path.join(SAMPLE_DATA_DIR, "premiere_example.xml")
SIMPLE_XML_PATH = os.path.join(SAMPLE_DATA_DIR, "sample_just_sequence.xml")


class AdaptersFcp7XmlTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(AdaptersFcp7XmlTest, self).__init__(*args, **kwargs)
        self.maxDiff = None

    def test_read(self):
        timeline = otio.adapters.read_from_file(FCP7_XML_EXAMPLE_PATH)

        self.assertTrue(timeline is not None)
        self.assertEqual(len(timeline.tracks), 7)

        video_tracks = [t for t in timeline.tracks
                        if t.kind == otio.schema.SequenceKind.Video]
        audio_tracks = [t for t in timeline.tracks
                        if t.kind == otio.schema.SequenceKind.Audio]

        self.assertEqual(len(video_tracks), 4)
        self.assertEqual(len(audio_tracks), 3)

        video_clip_names = (
            (None, 'sc01_sh010_anim.mov'),
            (None, 'sc01_sh010_anim.mov', None, 'sc01_sh020_anim.mov',
             'sc01_sh030_anim.mov', None, 'sc01_sh010_anim'),
            (None, 'test_title'),
            (None, 'sc01_master_layerA_sh030_temp.mov')
        )

        for n, track in enumerate(video_tracks):
            self.assertTupleEqual(tuple(c.name for c in track),
                                  video_clip_names[n])

        audio_clip_names = (
            (None, 'sc01_sh010_anim.mov', None, 'sc01_sh010_anim.mov'),
            (None, 'sc01_placeholder.wav', None, 'sc01_sh010_anim', None,
             'sc01_master_layerA_sh030_temp.mov'),
            (None, 'track_08.wav')
        )

        for n, track in enumerate(audio_tracks):
            self.assertTupleEqual(tuple(c.name for c in track),
                                  audio_clip_names[n])

        video_clip_durations = (
            ((536, 30.0), (100, 30.0)),
            ((13, 30.0), (100, 30.0), (52, 30.0), (157, 30.0), (235, 30.0),
             (79, 30.0), (320, 30.0)),
            ((13, 30.0), (943, 30.0)),
            ((956, 30.0), (124, 30.0))
        )

        for t, track in enumerate(video_tracks):
            for c, clip in enumerate(track):
                self.assertEqual(
                    clip.source_range.duration,
                    otio.opentime.RationalTime(*video_clip_durations[t][c])
                )

        audio_clip_durations = (
            ((13, 30.0), (100, 30.0), (423, 30.0), (100, 30.0)),
            ((335, 30.0), (170, 30.0), (131, 30.0), (286, 30.0), (34, 30.0),
             (124, 30.0)),
            ((153, 30.0), (198, 30.0))
        )

        for t, track in enumerate(audio_tracks):
            for c, clip in enumerate(track):
                self.assertEqual(
                    clip.source_range.duration,
                    otio.opentime.RationalTime(*audio_clip_durations[t][c])
                )

        timeline_marker_names = ('My MArker 1', 'dsf', None)

        for n, marker in enumerate(timeline.tracks.markers):
            self.assertEqual(marker.name, timeline_marker_names[n])

        timeline_marker_start_times = ((113, 30.0), (492, 30.0), (298, 30.0))

        for n, marker in enumerate(timeline.tracks.markers):
            self.assertEqual(
                marker.marked_range.start_time,
                otio.opentime.RationalTime(*timeline_marker_start_times[n])
            )

        timeline_marker_comments = ('so, this happened', 'fsfsfs', None)

        for n, marker in enumerate(timeline.tracks.markers):
            self.assertEqual(
                marker.metadata.get('fcp_xml', {}).get('comment'),
                timeline_marker_comments[n]
            )

        clip_with_marker = video_tracks[1][4]
        clip_marker = clip_with_marker.markers[0]
        self.assertEqual(clip_marker.name, None)
        self.assertEqual(clip_marker.marked_range.start_time,
                         otio.opentime.RationalTime(73, 30.0))
        self.assertEqual(
            clip_marker.metadata.get('fcp_xml', {}).get('comment'), None
        )

    def test_backreference_generator_read(self):
        with open(SIMPLE_XML_PATH, 'r') as fo:
            text = fo.read()

        adapt_mod = otio.adapters.from_name('fcp_xml').module()

        tree = cElementTree.fromstring(text)
        sequence = adapt_mod._get_single_sequence(tree)

        # make sure that element_map gets populated by the function calls in the 
        # way we want
        element_map = collections.defaultdict(dict)

        self.assertEqual(adapt_mod._parse_rate(sequence, element_map), 30.0)
        self.assertEqual(sequence, element_map["all_elements"]["sequence-1"])
        self.assertEqual(adapt_mod._parse_rate(sequence, element_map), 30.0)
        self.assertEqual(sequence, element_map["all_elements"]["sequence-1"])
        self.assertEqual(len(element_map["all_elements"].keys()), 1)

    def test_backreference_generator_write(self):

        adapt_mod = otio.adapters.from_name('fcp_xml').module()

        class dummy_obj(object):
            def __init__(self):
                self.attrib = {}

        @adapt_mod._backreference_build("test")
        def dummy_func(item, br_map):
            return dummy_obj()

        br_map = collections.defaultdict(dict)
        result_first = dummy_func("foo", br_map)
        self.assertNotEqual(br_map['test'], result_first)
        result_second = dummy_func("foo", br_map)
        self.assertNotEqual(result_first, result_second)

    def test_roundtrip_mem2disk2mem(self):
        timeline = otio.schema.Timeline('test_timeline')
        timeline.tracks.name = 'test_timeline'

        video_reference = otio.media_reference.External(
                target_url="/var/tmp/test1.mov",
                available_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(value=100, rate=24.0),
                    otio.opentime.RationalTime(value=1000, rate=24.0)
                )
            )
        audio_reference = otio.media_reference.External(
                target_url="/var/tmp/test1.wav",
                available_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(value=0, rate=24.0),
                    otio.opentime.RationalTime(value=1000, rate=24.0)
                )
            )

        v0 = otio.schema.Sequence(kind=otio.schema.sequence.SequenceKind.Video)
        v1 = otio.schema.Sequence(kind=otio.schema.sequence.SequenceKind.Video)

        timeline.tracks.extend([v0, v1])

        a0 = otio.schema.Sequence(kind=otio.schema.sequence.SequenceKind.Audio)

        timeline.tracks.append(a0)

        v0.extend([
            otio.schema.Clip(
                name='test_clip1',
                media_reference=video_reference,
                source_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(value=112, rate=24.0),
                    otio.opentime.RationalTime(value=40, rate=24.0)
                )
            ),
            otio.schema.Filler(
                source_range=otio.opentime.TimeRange(
                    duration=otio.opentime.RationalTime(value=60, rate=24.0)
                )
            ),
            otio.schema.Clip(
                name='test_clip2',
                media_reference=video_reference,
                source_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(value=123, rate=24.0),
                    otio.opentime.RationalTime(value=260, rate=24.0)
                )
            )
        ])

        v1.extend([
            otio.schema.Filler(
                source_range=otio.opentime.TimeRange(
                    duration=otio.opentime.RationalTime(value=500, rate=24.0)
                )
            ),
            otio.schema.Clip(
                name='test_clip3',
                media_reference=video_reference,
                source_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(value=112, rate=24.0),
                    otio.opentime.RationalTime(value=55, rate=24.0)
                )
            )
        ])

        a0.extend([
            otio.schema.Filler(
                source_range=otio.opentime.TimeRange(
                    duration=otio.opentime.RationalTime(value=10, rate=24.0)
                )
            ),
            otio.schema.Clip(
                name='test_clip4',
                media_reference=audio_reference,
                source_range=otio.opentime.TimeRange(
                    otio.opentime.RationalTime(value=152, rate=24.0),
                    otio.opentime.RationalTime(value=248, rate=24.0)
                )
            )
        ])

        timeline.tracks.markers.append(
            otio.schema.Marker(name='test_timeline_marker',
                               marked_range=otio.opentime.TimeRange(
                                   otio.opentime.RationalTime(123, 24.0)
                               ),
                               metadata={'fcp_xml': {'comment': 'my_comment'}})
        )

        v1[1].markers.append(
            otio.schema.Marker(name='test_clip_marker',
                               marked_range=otio.opentime.TimeRange(
                                   otio.opentime.RationalTime(125, 24.0)
                               ),
                               metadata={'fcp_xml': {'comment': 'my_comment'}})
        )

        result = otio.adapters.write_to_string(timeline,
                                               adapter_name='fcp_xml')
        new_timeline = otio.adapters.read_from_string(result,
                                                      adapter_name='fcp_xml')

        self.assertMultiLineEqual(
            otio.adapters.write_to_string(
                new_timeline, adapter_name="otio_json"
            ),
            otio.adapters.write_to_string(
                timeline, adapter_name="otio_json"
            )
        )

        self.assertEqual(new_timeline, timeline)

    def test_roundtrip_disk2mem2disk(self):
        timeline = otio.adapters.read_from_file(FCP7_XML_EXAMPLE_PATH)
        tmp_path = tempfile.mkstemp(suffix=".xml", text=True)[1]

        otio.adapters.write_to_file(timeline, tmp_path)
        result = otio.adapters.read_from_file(tmp_path)

        original_json = otio.adapters.write_to_string(timeline, 'otio_json')
        output_json = otio.adapters.write_to_string(result, 'otio_json')
        self.assertMultiLineEqual(original_json, output_json)

        self.assertEqual(timeline, result)

        # But the xml text on disk is not identical because otio has a subset
        # of features to xml and we drop all the nle specific preferences.
        raw_original = open(FCP7_XML_EXAMPLE_PATH, "r").read()
        raw_output = open(tmp_path, "r").read()
        self.assertNotEqual(raw_original, raw_output)


if __name__ == '__main__':
    unittest.main()