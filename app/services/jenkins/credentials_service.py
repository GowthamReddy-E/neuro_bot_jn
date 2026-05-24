import configparser
import os


def _instance_env_vars(instance):
    key = (instance or "default").upper().replace("-", "_").replace(".", "_")
    key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in key)
    return f"JENKINS_{key}_USERNAME", f"JENKINS_{key}_TOKEN"


def _read_credentials_from_env(instance="default"):
    user_var, token_var = _instance_env_vars(instance)
    username = os.getenv(user_var)
    token = os.getenv(token_var)
    if username and token:
        return username, token

    if instance != "default":
        user_var, token_var = _instance_env_vars("default")
        username = os.getenv(user_var)
        token = os.getenv(token_var)
        if username and token:
            return username, token

    raise ValueError(
        f"Missing Jenkins environment credentials for instance '{instance}'."
    )


def read_credentials(credentials_file=None, instance="default"):
    try:
        return _read_credentials_from_env(instance)
    except ValueError:
        pass

    if not credentials_file:
        raise ValueError(
            f"No credentials file provided and env credentials missing for instance '{instance}'"
        )

    config = configparser.ConfigParser()
    config.read(credentials_file)

    if instance in config:
        return config[instance]["username"], config[instance]["token"]

    if "default" in config:
        return config["default"]["username"], config["default"]["token"]

    sections = config.sections()
    if sections:
        fallback_instance = sections[0]
        return config[fallback_instance]["username"], config[fallback_instance]["token"]

    raise ValueError(f"No credentials found in '{credentials_file}'")


def get_job_credentials(job_name, job_config_file, credentials_file=None):
    config = configparser.ConfigParser()
    config.read(job_config_file)

    instance = "default"
    if job_name in config and "instance" in config[job_name]:
        instance = config[job_name]["instance"]

    return read_credentials(credentials_file, instance)
