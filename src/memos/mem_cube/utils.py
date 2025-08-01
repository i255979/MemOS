import copy
import logging
import subprocess
import tempfile

from memos.configs.mem_cube import GeneralMemCubeConfig


logger = logging.getLogger(__name__)


def download_repo(repo: str, base_url: str, dir: str | None = None) -> str:
    """Download a repository from a remote source.

    Args:
        repo (str): The repository name.
        base_url (str): The base URL of the remote repository.
        dir (str, optional): The directory where the repository will be downloaded. If None, a temporary directory will be created.
    If a directory is provided, it will be used instead of creating a temporary one.

    Returns:
        str: The local directory where the repository is downloaded.
    """
    if dir is None:
        dir = tempfile.mkdtemp()
    repo_url = f"{base_url}/{repo}"

    # Clone the repo
    subprocess.run(["git", "clone", repo_url, dir], check=True)

    return dir


def merge_config_with_default(
    existing_config: GeneralMemCubeConfig, default_config: GeneralMemCubeConfig
) -> GeneralMemCubeConfig:
    """
    Merge existing cube config with default config, preserving critical fields.

    This method updates general configuration fields (like API keys, model parameters)
    while preserving critical user-specific fields (like user_id, cube_id, graph_db settings).

    Args:
        existing_config (GeneralMemCubeConfig): The existing cube configuration loaded from file
        default_config (GeneralMemCubeConfig): The default configuration to merge from

    Returns:
        GeneralMemCubeConfig: Merged configuration
    """

    # Convert configs to dictionaries
    existing_dict = existing_config.model_dump(mode="json")
    default_dict = default_config.model_dump(mode="json")

    logger.info(
        f"Starting config merge for user {existing_config.user_id}, cube {existing_config.cube_id}"
    )

    # Define fields that should be preserved from existing config
    preserve_fields = {"user_id", "cube_id", "config_filename", "model_schema"}

    # Preserve graph_db from existing config if it exists, but merge some fields
    preserved_graph_db = None
    if "text_mem" in existing_dict and "text_mem" in default_dict:
        existing_text_config = existing_dict["text_mem"].get("config", {})
        default_text_config = default_dict["text_mem"].get("config", {})

        if "graph_db" in existing_text_config and "graph_db" in default_text_config:
            existing_graph_config = existing_text_config["graph_db"]["config"]
            default_graph_config = default_text_config["graph_db"]["config"]

            # Define graph_db fields to preserve (user-specific)
            preserve_graph_fields = {
                "auto_create",
                "user_name",
                "use_multi_db",
            }

            # Create merged graph_db config
            merged_graph_config = copy.deepcopy(existing_graph_config)
            for key, value in default_graph_config.items():
                if key not in preserve_graph_fields:
                    merged_graph_config[key] = value
                    logger.debug(
                        f"Updated graph_db field '{key}': {existing_graph_config.get(key)} -> {value}"
                    )
            if not default_graph_config.get("use_multi_db", True):
                # set original use_multi_db to False if default_graph_config.use_multi_db is False
                if merged_graph_config.get("use_multi_db", True):
                    merged_graph_config["use_multi_db"] = False
                    merged_graph_config["user_name"] = merged_graph_config.get("db_name")
                    merged_graph_config["db_name"] = default_graph_config.get("db_name")
                else:
                    logger.info("use_multi_db is already False, no need to change")

            preserved_graph_db = {
                "backend": existing_text_config["graph_db"]["backend"],
                "config": merged_graph_config,
            }

    # Use default config as base
    merged_dict = copy.deepcopy(default_dict)

    # Restore preserved fields from existing config
    for field in preserve_fields:
        if field in existing_dict:
            merged_dict[field] = existing_dict[field]
            logger.debug(f"Preserved field '{field}': {existing_dict[field]}")

    # Restore graph_db if it was preserved
    if preserved_graph_db and "text_mem" in merged_dict:
        merged_dict["text_mem"]["config"]["graph_db"] = preserved_graph_db
        logger.debug(f"Preserved graph_db with merged config: {preserved_graph_db}")

    # Create new config from merged dictionary
    merged_config = GeneralMemCubeConfig.model_validate(merged_dict)

    logger.info(
        f"Successfully merged cube config for user {merged_config.user_id}, cube {merged_config.cube_id}"
    )

    return merged_config
