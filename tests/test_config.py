import builtins
import imp
import mock
import os

mozphab = imp.load_source(
    "mozphab", os.path.join(os.path.dirname(__file__), os.path.pardir, "moz-phab")
)


def test_default_arc_command():
    _is_windows = mozphab.IS_WINDOWS

    mozphab.IS_WINDOWS = False
    config = mozphab.Config(should_access_file=False)
    assert config.arc_command == "arc"

    mozphab.IS_WINDOWS = True
    config = mozphab.Config(should_access_file=False)
    assert config.arc_command == "arc.bat"

    mozphab.IS_WINDOWS = _is_windows


@mock.patch("mozphab.Config.write")
@mock.patch("mozphab.os.path.exists")
def test_write_called(m_path_exists, m_write):
    m_path_exists.return_value = True
    config = mozphab.Config()
    m_write.assert_not_called()

    m_path_exists.return_value = False
    config = mozphab.Config()
    m_write.assert_called_once()


@mock.patch("mozphab.configparser.ConfigParser")
def test_set(m_configparser):
    config = mozphab.Config(should_access_file=False)

    config._set("a_section", "an_option", 1)
    config._config.add_section.assert_not_called()
    config._config.set.assert_called_once_with("a_section", "an_option", "1")

    config._config.reset_mock()
    config._config.has_section.return_value = False
    config._set("a_section", "an_option", 1)
    config._config.add_section.assert_called_once_with("a_section")
    config._config.set.assert_called_once_with("a_section", "an_option", "1")


@mock.patch("builtins.open")
@mock.patch("mozphab.os.path.exists")
@mock.patch("mozphab.configparser.ConfigParser")
@mock.patch("mozphab.Config._set")
def test_write(m_set, m_configparser, m_path_exists, m_open):
    config = mozphab.Config(should_access_file=False)

    m_path_exists.return_value = True
    config.write()
    assert 4 == len(m_set.call_args_list)
    m_open.assert_called_once()
    config._config.write.assert_called_once()

    m_set.reset_mock()
    m_open.reset_mock()
    config._config.reset_mock()
    m_path_exists.return_value = False
    config.write()
    assert 9 == len(m_set.call_args_list)
    m_open.assert_called_once()
    config._config.write.assert_called_once()
