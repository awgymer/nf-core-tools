import logging
import os
import shutil
from pathlib import Path

import yaml

from nf_core.modules.modules_json import ModulesJson
from nf_core.modules.modules_repo import ModulesRepo

from .components_utils import get_repo_type

log = logging.getLogger(__name__)


class ComponentCommand:
    """
    Base class for the 'nf-core modules' and 'nf-core subworkflows' commands
    """

    def __init__(self, component_type, dir, remote_url=None, branch=None, no_pull=False, hide_progress=False):
        """
        Initialise the ComponentClass object
        """
        self.component_type = ""
        self.dir = dir
        self.modules_repo = ModulesRepo(remote_url, branch, no_pull, hide_progress)
        self.hide_progress = hide_progress
        self.default_modules_path = Path("modules", "nf-core")
        self.default_tests_path = Path("tests", "modules", "nf-core")
        try:
            if self.dir:
                self.dir, self.repo_type = get_repo_type(self.dir)
            else:
                self.repo_type = None
        except LookupError as e:
            raise UserWarning(e)

    def get_modules_clone_modules(self):
        """
        Get the modules repository available in a clone of nf-core/modules
        """
        module_base_path = Path(self.dir, self.default_modules_path)
        return [
            str(Path(dir).relative_to(module_base_path))
            for dir, _, files in os.walk(module_base_path)
            if "main.nf" in files
        ]

    def has_valid_directory(self):
        """Check that we were given a pipeline or clone of nf-core/modules"""
        if self.repo_type == "modules":
            return True
        if self.dir is None or not os.path.exists(self.dir):
            log.error(f"Could not find pipeline: {self.dir}")
            return False
        main_nf = os.path.join(self.dir, "main.nf")
        nf_config = os.path.join(self.dir, "nextflow.config")
        if not os.path.exists(main_nf) and not os.path.exists(nf_config):
            raise UserWarning(f"Could not find a 'main.nf' or 'nextflow.config' file in '{self.dir}'")
        return True

    def has_modules_file(self):
        """Checks whether a module.json file has been created and creates one if it is missing"""
        modules_json_path = os.path.join(self.dir, "modules.json")
        if not os.path.exists(modules_json_path):
            log.info("Creating missing 'module.json' file.")
            ModulesJson(self.dir).create()

    def clear_module_dir(self, module_name, module_dir):
        """Removes all files in the module directory"""
        try:
            shutil.rmtree(module_dir)
            # Try cleaning up empty parent if tool/subtool and tool/ is empty
            if module_name.count("/") > 0:
                parent_dir = os.path.dirname(module_dir)
                try:
                    os.rmdir(parent_dir)
                except OSError:
                    log.debug(f"Parent directory not empty: '{parent_dir}'")
                else:
                    log.debug(f"Deleted orphan tool directory: '{parent_dir}'")
            log.debug(f"Successfully removed {module_name} module")
            return True
        except OSError as e:
            log.error(f"Could not remove module: {e}")
            return False

    def modules_from_repo(self, install_dir):
        """
        Gets the modules installed from a certain repository

        Args:
            install_dir (str): The name of the directory where modules are installed

        Returns:
            [str]: The names of the modules
        """
        repo_dir = Path(self.dir, "modules", install_dir)
        if not repo_dir.exists():
            raise LookupError(f"Nothing installed from {install_dir} in pipeline")

        return [
            str(Path(dir_path).relative_to(repo_dir)) for dir_path, _, files in os.walk(repo_dir) if "main.nf" in files
        ]

    def install_module_files(self, module_name, module_version, modules_repo, install_dir):
        """
        Installs a module into the given directory

        Args:
            module_name (str): The name of the module
            module_version (str): Git SHA for the version of the module to be installed
            modules_repo (ModulesRepo): A correctly configured ModulesRepo object
            install_dir (str): The path to where the module should be installed (should be the 'modules/' dir of the pipeline)

        Returns:
            (bool): Whether the operation was successful of not
        """
        return modules_repo.install_module(module_name, install_dir, module_version)

    def load_lint_config(self):
        """Parse a pipeline lint config file.

        Look for a file called either `.nf-core-lint.yml` or
        `.nf-core-lint.yaml` in the pipeline root directory and parse it.
        (`.yml` takes precedence).

        Add parsed config to the `self.lint_config` class attribute.
        """
        config_fn = os.path.join(self.dir, ".nf-core-lint.yml")

        # Pick up the file if it's .yaml instead of .yml
        if not os.path.isfile(config_fn):
            config_fn = os.path.join(self.dir, ".nf-core-lint.yaml")

        # Load the YAML
        try:
            with open(config_fn, "r") as fh:
                self.lint_config = yaml.safe_load(fh)
        except FileNotFoundError:
            log.debug(f"No lint config file found: {config_fn}")

    def check_modules_structure(self):
        """
        Check that the structure of the modules directory in a pipeline is the correct one:
            modules/nf-core/TOOL/SUBTOOL

        Prior to nf-core/tools release 2.6 the directory structure had an additional level of nesting:
            modules/nf-core/modules/TOOL/SUBTOOL
        """
        if self.repo_type == "pipeline":
            wrong_location_modules = []
            for directory, _, files in os.walk(Path(self.dir, "modules")):
                if "main.nf" in files:
                    module_path = Path(directory).relative_to(Path(self.dir, "modules"))
                    parts = module_path.parts
                    # Check that there are modules installed directly under the 'modules' directory
                    if parts[1] == "modules":
                        wrong_location_modules.append(module_path)
            # If there are modules installed in the wrong location
            if len(wrong_location_modules) > 0:
                log.info("The modules folder structure is outdated. Reinstalling modules.")
                # Remove the local copy of the modules repository
                log.info(f"Updating '{self.modules_repo.local_repo_dir}'")
                self.modules_repo.setup_local_repo(
                    self.modules_repo.remote_url, self.modules_repo.branch, self.hide_progress
                )
                # Move wrong modules to the right directory
                for module in wrong_location_modules:
                    modules_dir = Path("modules").resolve()
                    correct_dir = Path(modules_dir, self.modules_repo.repo_path, Path(*module.parts[2:]))
                    wrong_dir = Path(modules_dir, module)
                    shutil.move(wrong_dir, correct_dir)
                    log.info(f"Moved {wrong_dir} to {correct_dir}.")
                shutil.rmtree(Path(self.dir, "modules", self.modules_repo.repo_path, "modules"))
                # Regenerate modules.json file
                modules_json = ModulesJson(self.dir)
                modules_json.check_up_to_date()