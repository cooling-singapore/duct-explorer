from explorer.bdp.bdp import DUCTBaseDataPackageDB, bdp_spec
from saas.core.logging import Logging
from saas.sdk.cli.helpers import CLICommandGroup

from explorer.cli.base import BDPCreate, BDPRemove, BDPList

logger = Logging.get('explorer.cli')


class DUCTBDPCreate(BDPCreate):
    def __init__(self) -> None:
        super().__init__(bdp_spec, DUCTBaseDataPackageDB)


class DUCTCLICommandGroup(CLICommandGroup):
    def __init__(self):
        super().__init__('duct', 'DUCT-specific commands', commands=[
            CLICommandGroup('bdp', 'manage base data packages', commands=[
                DUCTBDPCreate(),
                BDPRemove(),
                BDPList()
            ])
        ])
