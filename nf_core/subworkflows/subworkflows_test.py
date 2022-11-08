#!/usr/bin/env python
"""
The SubworkflowsTest class runs the tests locally
"""

from nf_core.components.components_test import ComponentsTest


class SubworkflowsTest(ComponentsTest):
    """
    Class to run module pytests.
    """

    def __init__(
        self,
        subworkflow_name=None,
        no_prompts=False,
        pytest_args="",
        remote_url=None,
        branch=None,
        no_pull=False,
    ):
<<<<<<< HEAD
        self.subworkflow_name = subworkflow_name
        self.no_prompts = no_prompts
        self.pytest_args = pytest_args

        super().__init__(".", remote_url, branch, no_pull)

    def run(self):
        """Run test steps"""
        if not self.no_prompts:
            log.info(
                "[yellow]Press enter to use default values [cyan bold](shown in brackets) [yellow]or type your own responses"
            )
        self._check_inputs()
        self._set_profile()
        self._check_profile()
        self._run_pytests()

    def _check_inputs(self):
        """Do more complex checks about supplied flags."""
        # Retrieving installed subworkflows
        if self.repo_type == "modules":
            installed_subwf = self.get_components_clone_modules()
        else:
            modules_json = ModulesJson(self.dir)
            modules_json.check_up_to_date()
            installed_subwf = modules_json.get_installed_subworkflows().get(self.modules_repo.remote_url)

        # Get the subworkflow name if not specified
        if self.subworkflow_name is None:
            if self.no_prompts:
                raise UserWarning(
                    "Subworkflow name not provided and prompts deactivated. Please provide the Subworkflow name SUBWORKFLOW."
                )
            if not installed_subwf:
                raise UserWarning(
                    f"No installed subworkflows were found from '{self.modules_repo.remote_url}'.\n"
                    f"Are you running the tests inside the nf-core/modules main directory?\n"
                    f"Otherwise, make sure that the directory structure is subworkflows/SUBWORKFLOW/ and tests/subworkflows/SUBWORKFLOW/"
                )
            self.subworkflow_name = questionary.autocomplete(
                "Subworkflow name:",
                choices=installed_subwf,
                style=nf_core.utils.nfcore_question_style,
            ).unsafe_ask()

        # Sanity check that the module directory exists
        self._validate_folder_structure()

    def _validate_folder_structure(self):
        """Validate that the modules follow the correct folder structure to run the tests:
        - subworkflows/nf-core/SUBWORKFLOW/
        - tests/subworkflows/nf-core/SUBWORKFLOW/

        """
        subworkflow_path = self.paths.get_subworkflows_path() / self.subworkflow_name
        test_path = self.paths.get_subworkflows_tests_path() / self.subworkflow_name

        if not subworkflow_path.is_dir():
            raise UserWarning(
                f"Cannot find directory '{subworkflow_path.relative_to(self.paths.dir)}'. Should be SUBWORKFLOW. Are you running the tests inside the nf-core/modules main directory?"
            )
        if not test_path.is_dir():
            raise UserWarning(
                f"Cannot find directory '{test_path.relative_to(self.paths.dir)}'. Should be SUBWORKFLOW. "
                "Are you running the tests inside the nf-core/modules main directory? "
                "Do you have tests for the specified module?"
            )

    def _set_profile(self):
        """Set $PROFILE env variable.
        The config expects $PROFILE and Nextflow fails if it's not set.
        """
        if os.environ.get("PROFILE") is None:
            os.environ["PROFILE"] = ""
            if self.no_prompts:
                log.info(
                    "Setting environment variable '$PROFILE' to an empty string as not set.\n"
                    "Tests will run with Docker by default. "
                    "To use Singularity set 'export PROFILE=singularity' in your shell before running this command."
                )
            else:
                question = {
                    "type": "list",
                    "name": "profile",
                    "message": "Choose software profile",
                    "choices": ["Docker", "Singularity", "Conda"],
                }
                answer = questionary.unsafe_prompt([question], style=nf_core.utils.nfcore_question_style)
                profile = answer["profile"].lower()
                os.environ["PROFILE"] = profile
                log.info(f"Setting environment variable '$PROFILE' to '{profile}'")

    def _check_profile(self):
        """Check if profile is available"""
        profile = os.environ.get("PROFILE")
        # Make sure the profile read from the environment is a valid Nextflow profile.
        valid_nextflow_profiles = ["docker", "singularity", "conda"]
        if profile in valid_nextflow_profiles:
            if not which(profile):
                raise UserWarning(f"Command '{profile}' not found - is it installed?")
        else:
            raise UserWarning(
                f"The PROFILE '{profile}' set in the shell environment is not valid.\n"
                f"Valid Nextflow profiles are '{', '.join(valid_nextflow_profiles)}'."
            )

    def _run_pytests(self):
        """Given a subworkflow name, run tests."""
        # Print nice divider line
        console = rich.console.Console()
        console.rule(self.subworkflow_name, style="black")

        # Set pytest arguments
        command_args = ["--tag", f"{self.subworkflow_name}", "--symlink", "--keep-workflow-wd", "--git-aware"]
        command_args += self.pytest_args

        # Run pytest
        log.info(f"Running pytest for module '{self.subworkflow_name}'")
        sys.exit(pytest.main(command_args))
=======
        super().__init__(
            component_type="subworkflows",
            component_name=subworkflow_name,
            no_prompts=no_prompts,
            pytest_args=pytest_args,
            remote_url=remote_url,
            branch=branch,
            no_pull=no_pull,
        )
>>>>>>> dev
