# Copyright (c) 2025, the cclib development team
#
# This file is part of cclib (http://cclib.github.io) and is distributed under
# the terms of the BSD 3-Clause License.

"""Contains parsers for all supported programs"""

# ruff: noqa: F401
# These import statements are added for the convenience of users...
# Rather than having to type:
#         from cclib.parser.gaussianparser import Gaussian
# they can use:
#         from cclib.parser import Gaussian

# This allows users to type:
#         from cclib.parser import ccopen
from cclib.io.ccio import ccopen
from cclib.parser.adfparser import ADF
from cclib.parser.cfourparser import CFOUR
from cclib.parser.daltonparser import DALTON
from cclib.parser.data import ccData
from cclib.parser.fchkparser import FChk
from cclib.parser.gamessdatparser import GAMESSDAT
from cclib.parser.gamessparser import GAMESS
from cclib.parser.gamessukparser import GAMESSUK
from cclib.parser.gaussianparser import Gaussian
from cclib.parser.jaguarparser import Jaguar
from cclib.parser.molcasparser import Molcas
from cclib.parser.molproparser import Molpro
from cclib.parser.mopacparser import MOPAC
from cclib.parser.nboparser import NBO
from cclib.parser.nwchemparser import NWChem
from cclib.parser.orcaparser import ORCA
from cclib.parser.psi3parser import Psi3
from cclib.parser.psi4parser import Psi4
from cclib.parser.qchemparser import QChem
from cclib.parser.turbomoleparser import Turbomole
from cclib.parser.xtbparser import XTB
