import json
import os
import shutil
import tempfile
from typing import List, Dict
from zipfile import ZipFile

from duct.exceptions import DUCTRuntimeError
from explorer.dots.dot import DataObjectType, DOTVerificationMessage, DOTVerificationResult


class EMMEInputPackage(DataObjectType):
    DATA_TYPE = 'tememme.InputPackage'

    _REQUIRED_FILES = {"functions.txt", "modes.txt", "network.txt", "turns.txt",
                       "extra_links.txt", "extra_turns.txt", "extra_functions.txt",
                       "matrices.txt", "simulation_parameters.json"}

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'EMME Input Package'

    def supported_formats(self) -> List[str]:
        return ['zip']

    def extract_feature(self, content_path: str, parameters: dict) -> List[Dict]:
        return []

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Delta not supported")

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'zip':
            shutil.copyfile(content_path, export_path)
        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Delta not supported")

    def verify_parameters(self, directory: str) -> List[DOTVerificationMessage]:
        """
        `simulation_parameters.json` is a list containing dicts with the following properties:
        "mode": id for the type of vehicle, found in modes.txt (e.g. 'c'),
        "demand": id for the matrix containing the demand values, found in matrices.txt (e.g. 'mf20'),
        "generalized_cost": property name of generalized_cost, found in extra_links.txt (e.g. '@gccar')
        """
        messages = []

        params_path = os.path.join(directory, "simulation_parameters.json")
        modes_path = os.path.join(directory, "modes.txt")
        matrices_path = os.path.join(directory, "matrices.txt")
        extra_links_path = os.path.join(directory, "extra_links.txt")

        # Read params
        with open(params_path) as f:
            params = json.load(f)

        # Read required files
        modes = None
        if os.path.isfile(modes_path):
            with open(modes_path) as f:
                modes = f.read()
        matrices = None
        if os.path.isfile(matrices_path):
            with open(matrices_path) as f:
                matrices = f.read()
        extra_links = None
        if os.path.isfile(extra_links_path):
            with open(extra_links_path) as f:
                extra_links = f.read()

        # Verify params
        for i, param in enumerate(params):
            mode = param.get("mode")
            if mode is None:
                messages.append(
                    DOTVerificationMessage(
                        severity="error",
                        message=f"Parameter at index {i} does not have the property: `mode`"
                    )
                )
            elif f"a {mode} " not in modes:
                messages.append(
                    DOTVerificationMessage(
                        severity="error",
                        message=f"Required mode not found in mode.txt: `{mode}`"
                    )
                )

            matrix = param.get("demand")
            if matrix is None:
                messages.append(
                    DOTVerificationMessage(
                        severity="error",
                        message=f"Parameter at index {i} does not have the property: `demand`"
                    )
                )
            elif f"a matrix={matrix} " not in matrices:
                messages.append(
                    DOTVerificationMessage(
                        severity="error",
                        message=f"Required demand matrix not found in matrices.txt: `{matrix}`"
                    )
                )

            link_property = param.get("generalized_cost")
            if link_property is None:
                messages.append(
                    DOTVerificationMessage(
                        severity="error",
                        message=f"Parameter at index {i} does not have the property: `generalized_cost`"
                    )
                )
            elif f"{link_property} LINK " not in extra_links:
                messages.append(
                    DOTVerificationMessage(
                        severity="error",
                        message=f"Required link property not found in extra_links.txt: `{link_property}`"
                    )
                )

        return messages

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        messages = []
        is_verified = True

        with tempfile.TemporaryDirectory() as tmpdir:
            with ZipFile(content_path) as f:
                f.extractall(tmpdir)

            # Verify if required files exist
            missing_files = []
            for _file in os.listdir(tmpdir):
                if _file not in self._REQUIRED_FILES:
                    missing_files.append(_file)
            if len(missing_files):
                messages.append(
                    DOTVerificationMessage(
                        severity="error", message=f"Required files are missing: {', '.join(missing_files)}"
                    )
                )
                is_verified = False

            # Verify values in simulation parameters (naive way; as long as it exists in file)
            if "simulation_parameters.json" not in missing_files:
                _messages = self.verify_parameters(tmpdir)
                if len(_messages):
                    is_verified = False
                messages.extend(_messages)

        return DOTVerificationResult(
            messages=messages,
            is_verified=is_verified
        )
