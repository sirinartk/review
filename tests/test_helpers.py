import builtins
import datetime
import errno
import imp
import json
import mock
import os
import subprocess
import unittest

import pytest

mozphab = imp.load_source(
    "mozphab", os.path.join(os.path.dirname(__file__), os.path.pardir, "moz-phab")
)


def test_zulu_time():
    assert 1547809678 == mozphab.parse_zulu_time("2019-01-18T11:07:58Z")


@mock.patch("builtins.open")
@mock.patch("mozphab.json")
def test_read_json_field(m_json, m_open):
    m_open.side_effect = IOError(errno.ENOENT, "Not a file")
    assert None == mozphab.read_json_field(["nofile"], ["not existing"])

    m_open.side_effect = IOError(errno.ENOTDIR, "Not a directory")
    with pytest.raises(IOError):
        mozphab.read_json_field(["nofile"], ["not existing"])

    m_open.side_effect = ValueError()
    assert None == mozphab.read_json_field(["nofile"], ["not existing"])

    m_open.side_effect = None
    m_json.load.return_value = dict(a="value A", b=3)
    assert None == mozphab.read_json_field(["filename"], ["not existing"])
    assert "value A" == mozphab.read_json_field(["filename"], ["a"])

    m_json.load.side_effect = (
        dict(a="value A", b=3),
        dict(b="value B", c=dict(a="value CA")),
    )
    assert 3 == mozphab.read_json_field(["file_a", "file_b"], ["b"])
    m_json.load.side_effect = (
        dict(b="value B", c=dict(a="value CA")),
        dict(a="value A", b=3),
    )
    assert "value B" == mozphab.read_json_field(["file_b", "file_a"], ["b"])
    m_json.load.side_effect = (
        dict(a="value A", b=3),
        dict(b="value B", c=dict(a="value CA")),
    )
    assert "value CA" == mozphab.read_json_field(["file_a", "file_b"], ["c", "a"])


@mock.patch("subprocess.check_output")
def test_check_output(m_check_output):
    m_check_output.side_effect = subprocess.CalledProcessError(cmd="", returncode=1)
    with pytest.raises(mozphab.CommandError):
        mozphab.check_output(["command"])

    m_check_output.side_effect = ("response \nline \n",)
    assert ["response ", "line"] == mozphab.check_output(["command"])

    m_check_output.side_effect = ("response \nline \n",)
    assert ["response ", "line "] == mozphab.check_output(["command"], strip=False)

    m_check_output.side_effect = ("response \nline \n",)
    assert "response \nline" == mozphab.check_output(["command"], split=False)


@mock.patch.object(builtins, "input")
@mock.patch("mozphab.sys")
def test_prompt(m_sys, m_input):
    input_response = None

    def _input(_):
        return input_response

    m_input.side_effect = _input

    # Default
    input_response = ""
    assert "AAA" == mozphab.prompt("", ["AAA", "BBB"])

    # Escape
    m_sys.exit.side_effect = SystemExit()
    with pytest.raises(SystemExit):
        input_response = chr(27)
        mozphab.prompt("", ["AAA"])

    input_response = "aaa"
    assert "AAA" == mozphab.prompt("", ["AAA", "BBB"])
    input_response = "a"
    assert "AAA" == mozphab.prompt("", ["AAA", "BBB"])
    input_response = "b"
    assert "BBB" == mozphab.prompt("", ["AAA", "BBB"])


def test_git_find_repo(git_repo_path):
    path = str(git_repo_path)
    assert path == mozphab.find_repo_root(path)
    subdir = git_repo_path / "test_dir"
    subdir.mkdir()
    assert path == mozphab.find_repo_root(str(subdir))


def test_hg_find_repo(hg_repo_path):
    path = str(hg_repo_path)
    assert path == mozphab.find_repo_root(path)


def test_fail_find_repo():
    path = "/non/existing/path"
    assert mozphab.find_repo_root(path) is None


@mock.patch("mozphab.Mercurial")
@mock.patch("mozphab.Git")
def test_probe_repo(m_git, m_hg):
    m_hg.return_value = "HG"

    assert "HG" == mozphab.probe_repo("path")

    m_hg.side_effect = ValueError
    m_git.return_value = "GIT"
    assert "GIT" == mozphab.probe_repo("path")

    m_git.side_effect = ValueError
    assert mozphab.probe_repo("path") is None


@mock.patch("mozphab.probe_repo")
def test_repo_from_args(m_probe):
    # TODO test walking the path
    repo = None

    def probe_repo(path):
        return repo

    m_probe.side_effect = probe_repo

    class Args:
        def __init__(self, path=None):
            self.path = path

    with pytest.raises(mozphab.Error):
        mozphab.repo_from_args(Args(path="some path"))

    repo = mock.MagicMock()
    args = Args(path="some path")
    assert repo == mozphab.repo_from_args(args)
    repo.set_args.assert_called_once_with(args)


def test_arc_message():
    assert (
        "Title\n\nSummary:\nMessage\n\n\n\nTest Plan:\n\n"
        "Reviewers: reviewer\n\nSubscribers:\n\nBug #: 1"
        == mozphab.arc_message(
            dict(title="Title", body="Message", reviewers="reviewer", bug_id=1)
        )
    )

    assert (
        "Title\n\nSummary:\nMessage\n\nDepends on D123\n\nTest Plan:\n\n"
        "Reviewers: reviewer\n\nSubscribers:\n\nBug #: 1"
        == mozphab.arc_message(
            dict(
                title="Title",
                body="Message",
                reviewers="reviewer",
                bug_id=1,
                depends_on="Depends on D123",
            )
        )
    )

    assert (
        "\n\nSummary:\n\n\n\n\nTest Plan:\n\nReviewers: \n\nSubscribers:\n\nBug #: "
        == mozphab.arc_message(dict(title=None, body=None, reviewers=None, bug_id=None))
    )


def test_strip_differential_revision_from_commit_body():
    assert "" == mozphab.strip_differential_revision("\n\n")
    assert "" == mozphab.strip_differential_revision(
        "\nDifferential Revision: http://phabricator.test/D123"
    )

    assert "" == mozphab.strip_differential_revision(
        "Differential Revision: http://phabricator.test/D123"
    )

    assert "title" == mozphab.strip_differential_revision(
        "title\nDifferential Revision: http://phabricator.test/D123"
    )

    assert "title" == mozphab.strip_differential_revision(
        "title\n\nDifferential Revision: http://phabricator.test/D123"
    )

    assert "title\n\nsummary" == mozphab.strip_differential_revision(
        "title\n\nsummary\n\nDifferential Revision: http://phabricator.test/D123"
    )


def test_amend_commit_message_body_with_new_revision_url():
    assert (
        "\nDifferential Revision: http://phabricator.test/D123"
        == mozphab.amend_revision_url("", "http://phabricator.test/D123")
    )

    assert (
        "title\n\nDifferential Revision: http://phabricator.test/D123"
        == mozphab.amend_revision_url("title", "http://phabricator.test/D123")
    )

    assert (
        "\nDifferential Revision: http://phabricator.test/D123"
        == mozphab.amend_revision_url(
            "\nDifferential Revision: http://phabricator.test/D999",
            "http://phabricator.test/D123",
        )
    )


@mock.patch("mozphab.arc_out")
def test_valid_reviewers_in_phabricator_returns_no_errors(arc_out):
    # See https://phabricator.services.mozilla.com/api/user.search
    arc_out.side_effect = (
        # user.query
        json.dumps(
            {"error": None, "errorMessage": None, "response": [{"userName": "alice"}]}
        ),
        # project.search
        json.dumps(
            {
                "error": None,
                "errorMessage": None,
                "response": {
                    "data": [{"fields": {"slug": "user-group"}}],
                    "maps": {"slugMap": {"alias1": {}, "#alias2": {}}},
                },
            }
        ),
    )
    reviewers = dict(granted=[], request=["alice", "#user-group", "#alias1", "#alias2"])
    assert [] == mozphab.check_for_invalid_reviewers(reviewers, "")


@mock.patch("mozphab.arc_out")
def test_non_existent_reviewers_or_groups_generates_error_list(arc_out):
    ts = 1543622400
    ts_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    reviewers = dict(
        granted=[],
        request=[
            "alice",
            "goober",
            "goozer",
            "#user-group",
            "#goo-group",
            "#gon-group",
        ],
    )
    arc_out.side_effect = (
        # user.query
        json.dumps(
            {
                "error": None,
                "errorMessage": None,
                "response": [
                    dict(userName="alice"),
                    dict(
                        userName="goober", currentStatus="away", currentStatusUntil=ts
                    ),
                ],
            }
        ),
        # project.search
        json.dumps(
            {
                "error": None,
                "errorMessage": None,
                "response": {"data": [{"fields": {"slug": "user-group"}}]},
            }
        ),
    )
    expected_errors = [
        dict(name="goober", until=ts_str),
        dict(name="#gon-group"),
        dict(name="goozer"),
        dict(name="#goo-group"),
    ]
    response = mozphab.check_for_invalid_reviewers(reviewers, "")
    for error in expected_errors:
        assert error in response


@mock.patch("mozphab.arc_out")
def test_reviwer_case_sensitivity(arc_out):
    reviewers = dict(granted=[], request=["Alice", "#uSeR-gRoUp"])
    arc_out.side_effect = (
        # See https://phabricator.services.mozilla.com/conduit/method/user.query/
        json.dumps(
            {"error": None, "errorMessage": None, "response": [dict(userName="alice")]}
        ),
        # See https://phabricator.services.mozilla.com/conduit/method/project.search/
        json.dumps(
            {
                "error": None,
                "errorMessage": None,
                "response": {"data": [{"fields": {"slug": "user-group"}}]},
            }
        ),
    )
    assert [] == mozphab.check_for_invalid_reviewers(reviewers, "")


@mock.patch("mozphab.arc_out")
def test_api_call_with_no_errors_returns_api_response_json(arc_out):
    # fmt: off
    arc_out.return_value = json.dumps(
        {
            "error": None,
            "errorMessage": None,
            "response": {"data": "ok"}
        }
    )
    # fmt: on
    api_response = mozphab.arc_call_conduit("my.method", {}, "")

    assert api_response == {"data": "ok"}
    arc_out.assert_called_once_with(
        ["call-conduit", "my.method"],
        cwd="",
        log_output_to_console=False,
        stdin=mock.ANY,
    )


@mock.patch("mozphab.arc_out")
def test_api_call_with_error_raises_exception(arc_out):
    arc_out.return_value = json.dumps(
        {
            "error": "ERR-CONDUIT-CORE",
            "errorMessage": "**sad trombone**",
            "response": None,
        }
    )

    with pytest.raises(mozphab.ConduitAPIError) as err:
        mozphab.arc_call_conduit("my.method", {}, "")
        assert err.message == "**sad trombone**"


@mock.patch("mozphab.arc_out")
def test_arc_ping_with_invalid_certificate_returns_false(arc_out):
    arc_out.side_effect = mozphab.CommandError
    assert not mozphab.arc_ping("")
