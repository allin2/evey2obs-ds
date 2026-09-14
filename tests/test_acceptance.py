from evey2obs.acceptance import acceptance_report


def _complete_manifest() -> dict:
    return {
        "samples": [
            {"id": "bv", "source_type": "bilibili", "expect_success": True},
            {
                "id": "yt-sub",
                "source_type": "youtube",
                "expected_extraction_methods": ["official_subtitle"],
            },
            {
                "id": "yt-whisper",
                "source_type": "youtube",
                "expected_extraction_methods": ["whisper"],
            },
            {"id": "dy", "source_type": "douyin"},
            {"id": "xhs", "source_type": "xiaohongshu"},
            {
                "id": "xhs-missing-token",
                "source_type": "xiaohongshu",
                "expect_success": False,
                "expected_error": "SHARE_TOKEN_MISSING",
            },
            {"id": "wechat-text", "source_type": "wechat", "min_attachments": 0},
            {"id": "wechat-image", "source_type": "wechat", "min_attachments": 1},
            {
                "id": "xyz-notes",
                "source_type": "xiaoyuzhou",
                "expected_extraction_methods": ["show_notes"],
            },
            {
                "id": "xyz-audio",
                "source_type": "xiaoyuzhou",
                "expected_extraction_methods": ["whisper"],
            },
            {
                "id": "local-audio",
                "source_type": "local_file",
                "local_files": ["/private/audio.mp3"],
            },
            {
                "id": "local-video",
                "source_type": "local_file",
                "local_files": ["/private/video.mp4"],
            },
        ]
    }


def test_acceptance_report_marks_complete_matrix() -> None:
    report = acceptance_report(_complete_manifest())

    assert report["complete"] is True
    assert report["missing"] == []
    assert report["covered_case_count"] == report["required_case_count"]


def test_acceptance_report_lists_missing_cases_without_urls() -> None:
    report = acceptance_report(
        {
            "samples": [
                {
                    "id": "yt-sub",
                    "source_type": "youtube",
                    "text": "https://youtu.be/private?token=secret",
                    "expected_extraction_methods": ["official_subtitle"],
                }
            ]
        }
    )
    rendered = str(report)

    assert report["complete"] is False
    assert "bilibili_public_video" in report["missing"]
    assert "youtube_with_subtitles" not in report["missing"]
    assert "token=secret" not in rendered
