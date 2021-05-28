import os
import warnings

from django.core.exceptions import ImproperlyConfigured


# BASE_DIR is the project root (i.e., where manage.py lives)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))

# Default .env location (override with environment variable PROJECT_ENV_FILE)
ENV_FILE = os.path.abspath(os.path.join(BASE_DIR, ".env"))
ENV_DATA = {}  # Loaded env data


class UNSET(object):
    pass


def get_variable(var_name, default=UNSET):
    """Read the given variable name from the environment or the designated .env file."""

    if var_name in os.environ:
        return os.environ[var_name]

    env_path = _load_file()

    if var_name in ENV_DATA:
        return ENV_DATA[var_name]
    elif default is not UNSET:
        return default

    raise ImproperlyConfigured(
        "Provide a default, set the env variable {var!r}, or place it in the an env file "
        "(currently: {env_path!r}) as: {var}='VALUE'".format(
            var=var_name,
            env_path=env_path,
        )
    )


def _load_file():
    """
    Loads the environment's env or the default env into a cache. Returns early if the target file
    doesn't exist or if an env has already loaded.

    Returns the path to the env file that was loaded, or else None if the file didn't exist.
    """
    env_path = os.environ.get("PROJECT_ENV_FILE", ENV_FILE)
    env_path = os.path.abspath(env_path)

    if not os.path.exists(env_path):
        # warnings.warn("Invalid env path specified: {!r}".format(env_path))
        return env_path
    elif ENV_DATA:  # Already loaded
        return env_path

    # Drop existing data and reload
    ENV_DATA.clear()
    with open(env_path) as f:
        try:
            for i, line in enumerate(f):
                exec(line, {}, ENV_DATA)
        except Exception as e:
            raise ImproperlyConfigured(
                'Error evaluating "{env_path}", line {line}'
                "\n{exception_type}: {exception}".format(
                    env_path=env_path,
                    line=i + 1,
                    exception_type=e.__class__.__name__,
                    exception=e,
                )
            )

    return env_path
