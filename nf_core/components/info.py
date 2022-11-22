import logging
import os
from pathlib import Path

import questionary
import yaml
from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import nf_core.utils
from nf_core.components.components_command import ComponentCommand
from nf_core.modules.modules_json import ModulesJson
from nf_core.modules.modules_repo import NF_CORE_MODULES_REMOTE

from .components_utils import get_repo_type

log = logging.getLogger(__name__)


class ComponentInfo(ComponentCommand):
    """
    Class to print information of a module/subworkflow.

    Attributes
    ----------
    meta : YAML object
        stores the information from meta.yml file
    local_path : str
        path of the local modules/subworkflows
    remote_location : str
        remote repository URL
    local : bool
        indicates if the module/subworkflow is locally installed or not
    repo_type : str
        repository type. Can be either 'pipeline' or 'modules'
    modules_json : ModulesJson object
        contains 'modules.json' file information from a pipeline
    component_name : str
        name of the module/subworkflow to get information from

    Methods
    -------
    init_mod_name(component)
        Makes sure that we have a modules/subworkflows name
    get_component_info()
        Given the name of a module/subworkflow, parse meta.yml and print usage help
    get_local_yaml()
        Attempt to get the meta.yml file from a locally installed module/subworkflow
    get_remote_yaml()
        Attempt to get the meta.yml file from a remote repo
    generate_component_info_help()
        Take the parsed meta.yml and generate rich help
    """

    def __init__(
        self,
        component_type,
        pipeline_dir,
        component_name,
        remote_url=None,
        branch=None,
        no_pull=False,
    ):
        super().__init__(component_type, pipeline_dir, remote_url, branch, no_pull)
        self.meta = None
        self.local_path = None
        self.remote_location = None
        self.local = None

        # Quietly check if this is a pipeline or not
        if pipeline_dir:
            try:
                pipeline_dir, repo_type = get_repo_type(pipeline_dir, use_prompt=False)
                log.debug(f"Found {repo_type} repo: {pipeline_dir}")
            except UserWarning as e:
                log.debug(f"Only showing remote info: {e}")
                pipeline_dir = None

        if self.repo_type == "pipeline":
            # Check modules directory structure
            if self.component_type == "modules":
                self.check_modules_structure()
            # Check modules.json up to date
            self.modules_json = ModulesJson(self.dir)
            self.modules_json.check_up_to_date()
        else:
            self.modules_json = None
        self.component = self.init_mod_name(component_name)

    def init_mod_name(self, component):
        """
        Makes sure that we have a module/subworkflow name before proceeding.

        Args:
            module: str: Module name to check
        """
        if component is None:
            self.local = questionary.confirm(
                f"Is the {self.component_type[:-1]} locally installed?", style=nf_core.utils.nfcore_question_style
            ).unsafe_ask()
            if self.local:
                if self.repo_type == "modules":
                    components = self.get_components_clone_modules()
                else:
                    components = self.modules_json.get_all_components(self.component_type).get(
                        self.modules_repo.remote_url
                    )
                    components = [
                        component if dir == "nf-core" else f"{dir}/{component}" for dir, component in components
                    ]
                    if components is None:
                        raise UserWarning(
                            f"No {self.component_type[:-1]} installed from '{self.modules_repo.remote_url}'"
                        )
            else:
                components = self.modules_repo.get_avail_components(self.component_type)
            component = questionary.autocomplete(
                f"Please select a {self.component_type[:-1]}",
                choices=components,
                style=nf_core.utils.nfcore_question_style,
            ).unsafe_ask()
            while component not in components:
                log.info(f"'{component}' is not a valid {self.component_type[:-1]} name")
                component = questionary.autocomplete(
                    f"Please select a new {self.component_type[:-1]}",
                    choices=components,
                    style=nf_core.utils.nfcore_question_style,
                ).unsafe_ask()

        return component

    def get_component_info(self):
        """Given the name of a module/subworkflow, parse meta.yml and print usage help."""

        # Running with a local install, try to find the local meta
        if self.local:
            self.meta = self.get_local_yaml()

        # Either failed locally or in remote mode
        if not self.meta:
            self.meta = self.get_remote_yaml()

        # Could not find the meta
        if self.meta is False:
            raise UserWarning(f"Could not find {self.component_type[:-1]} '{self.component}'")

        return self.generate_component_info_help()

    def get_local_yaml(self):
        """Attempt to get the meta.yml file from a locally installed module/subworkflow.

        Returns:
            dict or bool: Parsed meta.yml found, False otherwise
        """

        if self.repo_type == "pipeline":
            # Try to find and load the meta.yml file
            component_base_path = Path(self.dir, self.component_type)
            # Check that we have any modules/subworkflows installed from this repo
            components = self.modules_json.get_all_components(self.component_type).get(self.modules_repo.remote_url)
            component_names = [component for _, component in components]
            if components is None:
                raise LookupError(f"No {self.component_type[:-1]} installed from {self.modules_repo.remote_url}")

            if self.component in component_names:
                install_dir = [dir for dir, module in components if module == self.component][0]
                comp_dir = Path(component_base_path, install_dir, self.component)
                meta_fn = Path(comp_dir, "meta.yml")
                if meta_fn.exists():
                    log.debug(f"Found local file: {meta_fn}")
                    with open(meta_fn, "r") as fh:
                        self.local_path = comp_dir
                        return yaml.safe_load(fh)

            log.debug(f"{self.component_type[:-1].title()} '{self.component}' meta.yml not found locally")
        else:
            component_base_path = Path(self.dir, self.component_type, "nf-core")
            if self.component in os.listdir(component_base_path):
                comp_dir = Path(component_base_path, self.component)
                meta_fn = Path(comp_dir, "meta.yml")
                if meta_fn.exists():
                    log.debug(f"Found local file: {meta_fn}")
                    with open(meta_fn, "r") as fh:
                        self.local_path = comp_dir
                        return yaml.safe_load(fh)
            log.debug(f"{self.component_type[:-1].title()} '{self.component}' meta.yml not found locally")

        return None

    def get_remote_yaml(self):
        """Attempt to get the meta.yml file from a remote repo.

        Returns:
            dict or bool: Parsed meta.yml found, False otherwise
        """
        # Check if our requested module/subworkflow is there
        if self.component not in self.modules_repo.get_avail_components(self.component_type):
            return False

        file_contents = self.modules_repo.get_meta_yml(self.component_type, self.component)
        if file_contents is None:
            return False
        self.remote_location = self.modules_repo.remote_url
        return yaml.safe_load(file_contents)

    def generate_component_info_help(self):
        """Take the parsed meta.yml and generate rich help.

        Returns:
            rich renderable
        """

        renderables = []

        # Intro panel
        intro_text = Text()
        if self.local_path:
            intro_text.append(Text.from_markup(f"Location: [blue]{self.local_path}\n"))
        elif self.remote_location:
            intro_text.append(
                Text.from_markup(
                    ":globe_with_meridians: Repository: "
                    f"{ '[link={self.remote_location}]' if self.remote_location.startswith('http') else ''}"
                    f"{self.remote_location}"
                    f"{'[/link]' if self.remote_location.startswith('http') else '' }"
                    "\n"
                )
            )

        if self.meta.get("tools"):
            tools_strings = []
            for tool in self.meta["tools"]:
                for tool_name, tool_meta in tool.items():
                    if "homepage" in tool_meta:
                        tools_strings.append(f"[link={tool_meta['homepage']}]{tool_name}[/link]")
                    else:
                        tools_strings.append(f"{tool_name}")
            intro_text.append(Text.from_markup(f":wrench: Tools: {', '.join(tools_strings)}\n", style="dim"))

        if self.meta.get("description"):
            intro_text.append(Text.from_markup(f":book: Description: {self.meta['description']}", style="dim"))

        renderables.append(
            Panel(
                intro_text,
                title=f"[bold]{self.component_type[:-1].title()}: [green]{self.component}\n",
                title_align="left",
            )
        )

        # Inputs
        if self.meta.get("input"):
            inputs_table = Table(expand=True, show_lines=True, box=box.MINIMAL_HEAVY_HEAD, padding=0)
            inputs_table.add_column(":inbox_tray: Inputs")
            inputs_table.add_column("Description")
            inputs_table.add_column("Pattern", justify="right", style="green")
            for input in self.meta["input"]:
                for key, info in input.items():
                    inputs_table.add_row(
                        f"[orange1 on black] {key} [/][dim i] ({info['type']})",
                        Markdown(info["description"] if info["description"] else ""),
                        info.get("pattern", ""),
                    )

            renderables.append(inputs_table)

        # Outputs
        if self.meta.get("output"):
            outputs_table = Table(expand=True, show_lines=True, box=box.MINIMAL_HEAVY_HEAD, padding=0)
            outputs_table.add_column(":outbox_tray: Outputs")
            outputs_table.add_column("Description")
            outputs_table.add_column("Pattern", justify="right", style="green")
            for output in self.meta["output"]:
                for key, info in output.items():
                    outputs_table.add_row(
                        f"[orange1 on black] {key} [/][dim i] ({info['type']})",
                        Markdown(info["description"] if info["description"] else ""),
                        info.get("pattern", ""),
                    )

            renderables.append(outputs_table)

        # Installation command
        if self.remote_location:
            cmd_base = f"nf-core {self.component_type}"
            if self.remote_location != NF_CORE_MODULES_REMOTE:
                cmd_base = f"nf-core {self.component_type} --git-remote {self.remote_location}"
            renderables.append(
                Text.from_markup(f"\n :computer:  Installation command: [magenta]{cmd_base} install {self.component}\n")
            )

        return Group(*renderables)
