# Copyright (c) 2025, the cclib development team
#
# This file is part of cclib (http://cclib.github.io) and is distributed under
# the terms of the BSD 3-Clause License.

"""Parser for GAMESS(US) output files"""

import re

from cclib.parser import logfileparser, utils

import numpy


class GAMESS(logfileparser.Logfile):
    """A GAMESS/Firefly log file."""

    # Used to index self.scftargets[].
    SCFRMS, SCFMAX, SCFENERGY = list(range(3))

    # Used to extact Dunning basis set names.
    dunningbas = {
        "CCD": "cc-pVDZ",
        "CCT": "cc-pVTZ",
        "CCQ": "cc-pVQZ",
        "CC5": "cc-pV5Z",
        "CC6": "cc-pV6Z",
        "ACCD": "aug-cc-pVDZ",
        "ACCT": "aug-cc-pVTZ",
        "ACCQ": "aug-cc-pVQZ",
        "ACC5": "aug-cc-pV5Z",
        "ACC6": "aug-cc-pV6Z",
        "CCDC": "cc-pCVDZ",
        "CCTC": "cc-pCVTZ",
        "CCQC": "cc-pCVQZ",
        "CC5C": "cc-pCV5Z",
        "CC6C": "cc-pCV6Z",
        "ACCDC": "aug-cc-pCVDZ",
        "ACCTC": "aug-cc-pCVTZ",
        "ACCQC": "aug-cc-pCVQZ",
        "ACC5C": "aug-cc-pCV5Z",
        "ACC6C": "aug-cc-pCV6Z",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(logname="GAMESS", *args, **kwargs)

    def __str__(self):
        """Return a string representation of the object."""
        return f"GAMESS log file {self.filename}"

    def __repr__(self):
        """Return a representation of the object."""
        return f'GAMESS("{self.filename}")'

    def normalisesym(self, label):
        """Normalise the symmetries used by GAMESS.

        To normalise, two rules need to be applied:
        (1) Occurences of U/G in the 2/3 position of the label
            must be lower-cased
        (2) Two single quotation marks must be replaced by a double
        """

        if label[1:] == "''":
            end = '"'
        else:
            end = label[1:].replace("U", "u").replace("G", "g")
        return label[0] + end

    def before_parsing(self):
        self.firststdorient = True  # Used to decide whether to wipe the atomcoords clean
        self.cihamtyp = "none"  # Type of CI Hamiltonian: saps or dets.
        self.scftype = "none"  # Type of SCF calculation: BLYP, RHF, ROHF, etc.

    def extract(self, inputfile, line):
        """Extract information from the file object inputfile."""

        # Extract the version number. If the calculation is from
        # Firefly, its version number comes before a line that looks
        # like the normal GAMESS version number...
        if "Firefly version" in line:
            match = re.search(r"Firefly version\s([\d.]*)\D*(\d*)\s*\*", line)
            if match:
                base_version, build = match.groups()
                package_version = f"{base_version}+{build}"
                self.metadata["package_version"] = package_version
                self.metadata["legacy_package_version"] = base_version
        if "GAMESS VERSION =" in line:
            # ...so avoid overwriting it if Firefly already set this field.
            if "package_version" not in self.metadata:
                tokens = line.split()
                day, month, year = tokens[4:7]
                possible_release = tokens[-2]
                # There may not be a (Rn) for the nth release that year, in
                # which case this index is the same as 7 (the year).
                if possible_release == year:
                    release = "1"
                else:
                    # `(R23)` -> 23
                    release = possible_release[2:-1]
                self.metadata["package_version"] = f"{year}.r{release}"
                self.metadata["legacy_package_version"] = f"{year}R{release}"

        if line[1:12] == "INPUT CARD>":
            return

        # extract the methods
        if line[1:7] == "SCFTYP":
            method = line.split()[0][7:]
            if len(self.metadata["methods"]) == 0:
                self.metadata["methods"].append(method)

        # extract the basis set name
        if line[5:11] == "GBASIS":
            basnm1 = line.split()[0][7:]
            if basnm1 in self.dunningbas:
                self.metadata["basis_set"] = self.dunningbas[basnm1]
            else:
                if basnm1 == "PM3" or basnm1 == "AM1":
                    self.metadata["methods"].append(basnm1)
                if basnm1 == "STO":
                    if line.split()[2] == "2":
                        self.metadata["basis_set"] = "STO-2G"
                    elif line.split()[2] == "3":
                        self.metadata["basis_set"] = "STO-3G"
                    elif line.split()[2] == "4":
                        self.metadata["basis_set"] = "STO-4G"
                    elif line.split()[2] == "5":
                        self.metadata["basis_set"] = "STO-5G"
                if basnm1 == "N21":
                    if line.split()[2] == "3" and line.split()[3] == "POLAR=COMMON":
                        self.metadata["basis_set"] = "3-21G*"
                    if line.split()[2] == "3" and line.split()[3] == "POLAR=NONE":
                        self.metadata["basis_set"] = "3-21G"
                    if line.split()[2] == "4" and line.split()[3] == "POLAR=NONE":
                        self.metadata["basis_set"] = "4-21G"
                    if line.split()[2] == "6" and line.split()[3] == "POLAR=NONE":
                        self.metadata["basis_set"] = "6-21G"
                if basnm1 == "N31":
                    if line.split()[2] == "6" and (
                        line.split()[3] == "POLAR=POPN31" or line.split()[3] == "POLAR=POPLE"
                    ):
                        self.metadata["basis_set"] = "6-31G*"
                        line = next(inputfile)
                        if line.split()[-1] == "T":
                            self.metadata["basis_set"] = "6-31+G*"
                            line = next(inputfile)
                            if line.split()[1] == "0" and line.split()[3] == "T":
                                self.metadata["basis_set"] = "6-31++G*"
                            if line.split()[1] == "1" and line.split()[3] == "T":
                                self.metadata["basis_set"] = "6-31++G**"
                        else:
                            line = next(inputfile)
                            if line.split()[1] == "1":  # NPFUNC = 1
                                self.metadata["basis_set"] = "6-31G**"
                    if line.split()[2] == "6" and line.split()[3] == "POLAR=NONE":
                        self.metadata["basis_set"] = "6-31G"
                    if line.split()[2] == "4" and line.split()[3] == "POLAR=NONE":
                        self.metadata["basis_set"] = "4-31G"
                    if line.split()[2] == "4" and line.split()[3] == "POLAR=POPN31":
                        self.metadata["basis_set"] = "4-31G*"
                if basnm1 == "N311":
                    if line.split()[2] == "6" and line.split()[3] == "POLAR=POPN311":
                        self.metadata["basis_set"] = "6-311G*"
                        line = next(inputfile)
                        if line.split()[-1] == "T":
                            self.metadata["basis_set"] = "6-311+G*"
                            line = next(inputfile)
                            if line.split()[1] == "0" and line.split()[3] == "T":
                                self.metadata["basis_set"] = "6-311++G*"
                            if line.split()[1] == "1" and line.split()[3] == "T":
                                self.metadata["basis_set"] = "6-311++G**"
                        else:
                            line = next(inputfile)
                            if line.split()[1] == "1":  # NPFUNC = 1
                                self.metadata["basis_set"] = "6-311G**"
                    if line.split()[2] == "6" and line.split()[3] == "POLAR=NONE":
                        self.metadata["basis_set"] = "6-311G"

        # Symmetry: point group
        if " THE POINT GROUP OF THE MOLECULE IS" in line:
            pg = line.split()[-1]
            line = next(inputfile)
            order = line.split()[-1]
            point_group_full = pg.replace("N", order).lower()
            # TODO It appears that GAMESS does not reduce to the
            # largest Abelian subgroup.
            point_group_abelian = point_group_full
            self.metadata["symmetry_detected"] = point_group_full
            self.metadata["symmetry_used"] = point_group_abelian

        # Symmetry: ordering of irreducible representations
        if line.strip() == "DIMENSIONS OF THE SYMMETRY SUBSPACES ARE":
            line = next(inputfile)
            symlabels = [self.normalisesym(label) for label in line.split()[::3]]  # noqa: F841

        # We are looking for this line:
        #           PARAMETERS CONTROLLING GEOMETRY SEARCH ARE
        #           ...
        #           OPTTOL = 1.000E-04          RMIN   = 1.500E-03
        if line[10:18] == "OPTTOL =":
            if not hasattr(self, "geotargets"):
                opttol = float(line.split()[2])
                self.geotargets = numpy.array([opttol, 3.0 / opttol], "d")

        # Has to deal with such lines as:
        #  FINAL R-B3LYP ENERGY IS     -382.0507446475 AFTER  10 ITERATIONS
        #  FINAL ENERGY IS     -379.7594673378 AFTER   9 ITERATIONS
        # ...so take the number after the "IS"
        if line.find("FINAL") == 1:
            temp = line.split()
            self.append_attribute("scfenergies", float(temp[temp.index("IS") + 1]))
        # Empirical dispersion: first is GAMESS-US, second is Firefly
        if any(
            line.find(dispersion_trigger) == 1
            for dispersion_trigger in (
                "GRIMME'S DISPERSION ENERGY",
                "Dispersion correction to total energy",
            )
        ):
            self.append_attribute("dispersionenergies", float(line.split()[-1]))

        # For total energies after Moller-Plesset corrections, the output looks something like this:
        #
        # RESULTS OF MOLLER-PLESSET 2ND ORDER CORRECTION ARE
        #         E(0)=      -285.7568061536
        #         E(1)=         0.0
        #         E(2)=        -0.9679419329
        #       E(MP2)=      -286.7247480864
        # where E(MP2) = E(0) + E(2)
        #
        # With GAMESS-US 12 Jan 2009 (R3), the preceding text is different:
        #      DIRECT 4-INDEX TRANSFORMATION
        #      SCHWARZ INEQUALITY TEST SKIPPED          0 INTEGRAL BLOCKS
        #                     E(SCF)=       -76.0088477471
        #                       E(2)=        -0.1403745370
        #                     E(MP2)=       -76.1492222841
        #
        # With GAMESS-US 20 APR 2017 (R1), the following block may be present:
        #       SCHWARZ INEQUALITY TEST SKIPPED          0 INTEGRAL BLOCKS
        # ... END OF INTEGRAL TRANSFORMATION ...

        if (
            line.find("RESULTS OF MOLLER-PLESSET") >= 0
            or line[6:37] == "SCHWARZ INEQUALITY TEST SKIPPED"
        ):
            if not hasattr(self, "mpenergies"):
                self.mpenergies = []

            line = next(inputfile)
            # Each iteration has a new print-out
            if "END OF INTEGRAL TRANSFORMATION" not in line:
                self.mpenergies.append([])

                # GAMESS-US presently supports only second order corrections (MP2)
                # PC GAMESS also has higher levels (3rd and 4th), with different output
                # Only the highest level MP4 energy is gathered (SDQ or SDTQ)
                # Loop breaks when substring "DONE WITH MPn ENERGY" is encountered,
                # where n=2, 3 or 4.
                while "DONE WITH MP" not in line:
                    if len(line.split()) > 0:
                        # Only up to MP2 correction
                        if line.split()[0] == "E(MP2)=":
                            self.metadata["methods"].append("MP2")
                            self.mpenergies[-1].append(float(line.split()[1]))
                        # MP2 before higher order calculations
                        if line.split()[0] == "E(MP2)":
                            self.mpenergies[-1].append(float(line.split()[2]))
                        if line.split()[0] == "E(MP3)":
                            self.metadata["methods"].append("MP3")
                            self.mpenergies[-1].append(float(line.split()[2]))
                        if line.split()[0] in ["E(MP4-SDQ)", "E(MP4-SDTQ)"]:
                            self.metadata["methods"].append("MP4")
                            self.mpenergies[-1].append(float(line.split()[2]))
                    line = next(inputfile)

        # Total energies after Coupled Cluster calculations
        # Only the highest Coupled Cluster level result is gathered
        if line[12:23] == "CCD ENERGY:":
            self.metadata["methods"].append("CCD")
            self.append_attribute("ccenergies", float(line.split()[2]))
        if line.find("CCSD") >= 0 and line.split()[0:2] == ["CCSD", "ENERGY:"]:
            self.metadata["methods"].append("CCSD")
            if not hasattr(self, "ccenergies"):
                self.ccenergies = []
            ccenergy = float(line.split()[2])
            line = next(inputfile)
            if line[8:23] == "CCSD[T] ENERGY:":
                self.metadata["methods"].append("CCSD[T]")
                ccenergy = float(line.split()[2])
                line = next(inputfile)
                if line[8:23] == "CCSD(T) ENERGY:":
                    self.metadata["methods"].append("CCSD(T)")
                    ccenergy = float(line.split()[2])
            self.ccenergies.append(ccenergy)

        if "T1 DIAGNOSTIC" in line:
            self.metadata["t1_diagnostic"] = float(line.split()[3])

        # Also collect MP2 energies, which are always calculated before CC
        if line[8:23] == "MBPT(2) ENERGY:":
            self.append_attribute("mpenergies", [float(line.split()[2])])

        # Extract charge and multiplicity
        if line[1:19] == "CHARGE OF MOLECULE":
            charge = int(round(float(line.split()[-1])))
            self.set_attribute("charge", charge)

            line = next(inputfile)
            mult = int(line.split()[-1])
            self.set_attribute("mult", mult)

        # Electronic transitions (etenergies) for CIS runs and TD-DFT, which
        # have very similar outputs. The outputs EOM look very differentm, though.
        #
        #  ---------------------------------------------------------------------
        #                    CI-SINGLES EXCITATION ENERGIES
        #  STATE       HARTREE        EV      KCAL/MOL       CM-1         NM
        #  ---------------------------------------------------------------------
        #   1A''   0.1677341781     4.5643    105.2548      36813.40     271.64
        #   ...
        if re.match("(CI-SINGLES|TDDFT) EXCITATION ENERGIES", line.strip()):
            get_etosc = False
            header = next(inputfile).rstrip()
            if header.endswith("OSC. STR."):
                # water_cis_dets.out does not have the oscillator strength
                # in this table...it is extracted from a different section below
                get_etosc = True
                self.etoscs = []

            self.skip_line(inputfile, "dashes")

            line = next(inputfile)
            broken = line.split()
            while len(broken) > 0:
                # Take hartree value with more digits.
                # Note that the values listed after this are also less exact!
                self.append_attribute("etenergies", float(broken[1]))
                if get_etosc:
                    etosc = float(broken[-1])
                    self.etoscs.append(etosc)
                broken = next(inputfile).split()

        # Detect the CI hamiltonian type, if applicable.
        # Should always be detected if CIS is done.
        if line[8:64] == "RESULTS FROM SPIN-ADAPTED ANTISYMMETRIZED PRODUCT (SAPS)":
            self.cihamtyp = "saps"
        if line[8:64] == "RESULTS FROM DETERMINANT BASED ATOMIC ORBITAL CI-SINGLES":
            self.cihamtyp = "dets"

        # etsecs (used only for CIS runs for now)
        if line[1:14] == "EXCITED STATE":
            statenumber = int(line.split()[2])
            spin = int(float(line.split()[7]))
            if spin == 0:
                sym = "Singlet"
            if spin == 1:
                sym = "Triplet"
            sym += "-" + line.split()[-1]
            self.append_attribute("etsyms", sym)
            self.skip_lines(inputfile, ["b", "d", "EXCITATION", "FROM TO", "d"])
            line = next(inputfile)
            CIScontribs = []
            while line.strip()[0] != "-":
                MOtype = 0
                # alpha/beta are specified for hamtyp=dets
                if self.cihamtyp == "dets":
                    if line.split()[0] == "BETA":
                        MOtype = 1
                fromMO = int(line.split()[-3]) - 1
                toMO = int(line.split()[-2]) - 1
                coeff = float(line.split()[-1])
                # With the SAPS hamiltonian, the coefficients are multiplied
                #   by sqrt(2) so that they normalize to 1.
                # With DETS, both alpha and beta excitations are printed.
                # if self.cihamtyp == "saps":
                #    coeff /= numpy.sqrt(2.0)
                CIScontribs.append([(fromMO, MOtype), (toMO, MOtype), coeff])
                line = next(inputfile)
            self.append_attribute("etsecs", CIScontribs)

        # etoscs (used only for CIS runs now)
        if line[1:50] == "TRANSITION FROM THE GROUND STATE TO EXCITED STATE":
            # This was the suggested as a fix in issue #61, and it does allow
            # the parser to finish without crashing. However, it seems that
            # etoscs is shorter in this case than the other transition attributes,
            # so that should be somehow corrected and tested for.
            if "OPTICALLY" in line:
                pass
            else:
                statenumber = int(line.split()[-1])  # noqa: F841
                self.skip_lines(
                    inputfile,
                    [
                        "b",
                        "MULTIPLICITIES",
                        "STATE ENERGIES",
                        "EXCITATION ENERGY",
                        "X Y Z NORM",
                        "TDIP a.u.",
                        "TDIP D",
                    ],
                )
                line = next(inputfile)
                strength = float(line.split()[3])
                self.append_attribute("etoscs", strength)

        # TD-DFT for GAMESS-US.
        # The format for excitations has changed a bit between 2007 and 2012.
        # Original format parser was written for:
        #
        #          -------------------
        #          TRIPLET EXCITATIONS
        #          -------------------
        #
        # STATE #   1  ENERGY =    3.027228 EV
        # OSCILLATOR STRENGTH =    0.000000
        #        DRF    COEF       OCC      VIR
        #        ---    ----       ---      ---
        #         35 -1.105383     35  ->   36
        #         69 -0.389181     34  ->   37
        #        103 -0.405078     33  ->   38
        #        137  0.252485     32  ->   39
        #        168 -0.158406     28  ->   40
        #
        # STATE #   2  ENERGY =    4.227763 EV
        # ...
        #
        # Here is the corresponding 2012 version:
        #
        #          -------------------
        #          TRIPLET EXCITATIONS
        #          -------------------
        #
        # STATE #   1  ENERGY =    3.027297 EV
        # OSCILLATOR STRENGTH =    0.000000
        # LAMBDA DIAGNOSTIC   =    0.925 (RYDBERG/CHARGE TRANSFER CHARACTER)
        # SYMMETRY OF STATE   =    A
        #                 EXCITATION  DE-EXCITATION
        #     OCC     VIR  AMPLITUDE      AMPLITUDE
        #      I       A     X(I->A)        Y(A->I)
        #     ---     ---   --------       --------
        #     35      36   -0.929190      -0.176167
        #     34      37   -0.279823      -0.109414
        # ...
        #
        # We discern these two by the presence of the arrow in the old version.
        #
        # The "LET EXCITATIONS" pattern used below catches both
        # singlet and triplet excitations output.
        if line[14:29] == "LET EXCITATIONS":
            self.etenergies = []
            self.etoscs = []
            self.etsecs = []
            etsyms = []

            self.skip_lines(inputfile, ["d", "b"])

            # Loop while states are still being printed.
            line = next(inputfile)
            while line[1:6] == "STATE":
                self.updateprogress(inputfile, "Excited States")

                etenergy = utils.convertor(float(line.split()[-2]), "eV", "hartree")
                etoscs = float(next(inputfile).split()[-1])
                self.etenergies.append(etenergy)
                self.etoscs.append(etoscs)

                # Symmetry is not always present, especially in old versions.
                # Newer versions, on the other hand, can also provide a line
                # with lambda diagnostic and some extra headers.
                line = next(inputfile)
                if "LAMBDA DIAGNOSTIC" in line:
                    line = next(inputfile)
                if "SYMMETRY" in line:
                    etsyms.append(line.split()[-1])
                    line = next(inputfile)
                if "EXCITATION" in line and "DE-EXCITATION" in line:
                    line = next(inputfile)
                if line.count("AMPLITUDE") == 2:
                    line = next(inputfile)

                self.skip_line(inputfile, "dashes")

                CIScontribs = []
                line = next(inputfile)
                while line.strip():
                    cols = line.split()
                    if "->" in line:
                        i_occ_vir = [2, 4]
                        i_coeff = 1

                    else:
                        i_occ_vir = [0, 1]
                        i_coeff = 2
                    fromMO, toMO = (int(cols[i]) - 1 for i in i_occ_vir)
                    coeff = float(cols[i_coeff])
                    CIScontribs.append([(fromMO, 0), (toMO, 0), coeff])
                    line = next(inputfile)
                self.etsecs.append(CIScontribs)
                line = next(inputfile)

            # The symmetries are not always present.
            if etsyms:
                self.etsyms = etsyms

        # Maximum and RMS gradients.
        if "MAXIMUM GRADIENT" in line or "RMS GRADIENT" in line:
            parts = line.split()

            # Avoid parsing the following...

            ## YOU SHOULD RESTART "OPTIMIZE" RUNS WITH THE COORDINATES
            ## WHOSE ENERGY IS LOWEST.  RESTART "SADPOINT" RUNS WITH THE
            ## COORDINATES WHOSE RMS GRADIENT IS SMALLEST.  THESE ARE NOT
            ## ALWAYS THE LAST POINT COMPUTED!

            if parts[0] not in ["MAXIMUM", "RMS", "(1)"]:
                return

            if not hasattr(self, "geovalues"):
                self.geovalues = []

            # Newer versions (around 2006) have both maximum and RMS on one line:
            #       MAXIMUM GRADIENT =  0.0531540    RMS GRADIENT = 0.0189223
            if len(parts) == 8:
                maximum = float(parts[3])
                rms = float(parts[7])

            # In older versions of GAMESS, this spanned two lines, like this:
            #       MAXIMUM GRADIENT =    0.057578167
            #           RMS GRADIENT =    0.027589766
            if len(parts) == 4:
                maximum = float(parts[3])
                line = next(inputfile)
                parts = line.split()
                rms = float(parts[3])

            # FMO also prints two final one- and two-body gradients (see exam37):
            #   (1) MAXIMUM GRADIENT =  0.0531540    RMS GRADIENT = 0.0189223
            if len(parts) == 9:
                maximum = float(parts[4])
                rms = float(parts[8])

            self.geovalues.append([maximum, rms])

        # This is the input orientation, which is the only data available for
        # SP calcs, but which should be overwritten by the standard orientation
        # values, which is the only information available for all geoopt cycles.
        if line[11:50] == "ATOMIC                      COORDINATES":
            if not hasattr(self, "atomcoords"):
                self.atomcoords = []

            line = next(inputfile)
            atomcoords = []
            atomnos = []
            line = next(inputfile)
            while line.strip():
                temp = line.strip().split()
                atomcoords.append(
                    [utils.convertor(float(x), "bohr", "Angstrom") for x in temp[2:5]]
                )
                atomnos.append(
                    int(round(float(temp[1])))
                )  # Don't use the atom name as this is arbitary
                line = next(inputfile)

            self.set_attribute("atomnos", atomnos)
            self.atomcoords.append(atomcoords)

        if line[12:40] == "EQUILIBRIUM GEOMETRY LOCATED":
            # Prevent extraction of the final geometry twice
            if not hasattr(self, "optdone"):
                self.optdone = []
            self.optdone.append(len(self.geovalues) - 1)

        # Make sure we always have optdone for geomtry optimization, even if not converged.
        if "GEOMETRY SEARCH IS NOT CONVERGED" in line:
            if not hasattr(self, "optdone"):
                self.optdone = []

        # This is the standard orientation, which is the only coordinate
        # information available for all geometry optimisation cycles.
        # The input orientation will be overwritten if this is a geometry optimisation
        # We assume that a previous Input Orientation has been found and
        # used to extract the atomnos
        if line[1:29] == "COORDINATES OF ALL ATOMS ARE" and (
            not hasattr(self, "optdone") or self.optdone == []
        ):
            self.updateprogress(inputfile, "Coordinates")

            if self.firststdorient:
                self.firststdorient = False
                # Wipes out the single input coordinate at the start of the file
                self.atomcoords = []

            self.skip_lines(inputfile, ["line", "-"])

            atomcoords = []
            line = next(inputfile)

            for _ in range(self.natom):
                temp = line.strip().split()
                atomcoords.append(list(map(float, temp[2:5])))
                line = next(inputfile)
            self.atomcoords.append(atomcoords)

        # Section with SCF information.
        #
        # The space at the start of the search string is to differentiate from MCSCF.
        # Everything before the search string is stored as the type of SCF.
        # SCF types may include: BLYP, RHF, ROHF, UHF, etc.
        #
        # For example, in exam17 the section looks like this (note that this is GVB):
        #          ------------------------
        #          ROHF-GVB SCF CALCULATION
        #          ------------------------
        # GVB STEP WILL USE    119875 WORDS OF MEMORY.
        #
        #     MAXIT=  30   NPUNCH= 2   SQCDF TOL=1.0000E-05
        #     NUCLEAR ENERGY=        6.1597411978
        #     EXTRAP=T   DAMP=F   SHIFT=F   RSTRCT=F   DIIS=F  SOSCF=F
        #
        # ITER EX     TOTAL ENERGY       E CHANGE        SQCDF       DIIS ERROR
        #   0  0      -38.298939963   -38.298939963   0.131784454   0.000000000
        #   1  1      -38.332044339    -0.033104376   0.026019716   0.000000000
        # ... and will be terminated by a blank line.
        if line.rstrip()[-16:] == " SCF CALCULATION":
            # Remember the type of SCF.
            self.scftype = line.strip()[:-16]

            self.skip_line(inputfile, "dashes")

            while line[:5] != " ITER":
                self.updateprogress(inputfile, "Attributes")

                # GVB uses SQCDF for checking convergence (for example in exam17).
                if "GVB" in self.scftype and "SQCDF TOL=" in line:
                    scftarget = float(line.split("=")[-1])

                # Normally, however, the density is used as the convergence criterium.
                # Deal with various versions:
                #   (GAMESS VERSION = 12 DEC 2003)
                #     DENSITY MATRIX CONV=  2.00E-05  DFT GRID SWITCH THRESHOLD=  3.00E-04
                #   (GAMESS VERSION = 22 FEB 2006)
                #     DENSITY MATRIX CONV=  1.00E-05
                #   (PC GAMESS version 6.2, Not DFT?)
                #     DENSITY CONV=  1.00E-05
                elif "DENSITY CONV" in line or "DENSITY MATRIX CONV" in line:
                    scftarget = float(line.split()[-1])

                line = next(inputfile)

            if not hasattr(self, "scftargets"):
                self.scftargets = []

            self.scftargets.append([scftarget])

            if not hasattr(self, "scfvalues"):
                self.scfvalues = []

            # Normally the iterations print in 6 columns.
            # For ROHF, however, it is 5 columns, thus this extra parameter.
            if "ROHF" in self.scftype:
                self.scf_valcol = 4
            else:
                self.scf_valcol = 5

            line = next(inputfile)

            # SCF iterations are terminated by a blank line.
            # The first four characters usually contains the step number.
            # However, lines can also contain messages, including:
            #   * * *   INITIATING DIIS PROCEDURE   * * *
            #   CONVERGED TO SWOFF, SO DFT CALCULATION IS NOW SWITCHED ON
            #   DFT CODE IS SWITCHING BACK TO THE FINER GRID
            values = []
            while line.strip():
                try:
                    temp = int(line[0:4])
                except ValueError:
                    pass
                else:
                    # if there were 100 iterations or more, the first part of the line
                    # will look like 10099, 101100, 102101, etc., with no spaces between
                    # the numbers. We can check if this is the case by seeing if the first
                    # number on the line exceeds 10000.
                    split_line = [line[0:4], line[4:7]] + line[7:].split()
                    values.append([float(split_line[self.scf_valcol])])
                try:
                    line = next(inputfile)
                except StopIteration:
                    self.logger.warning("File terminated before end of last SCF!")
                    break
            self.scfvalues.append(values)

        # Sometimes, only the first SCF cycle has the banner parsed for above,
        # so we must identify them from the header before the SCF iterations.
        # The example we have for this is the GeoOpt unittest for Firefly8.
        if line[1:8] == "ITER EX":
            # In this case, the convergence targets are not printed, so we assume
            # they do not change.
            self.scftargets.append(self.scftargets[-1])

            values = []
            line = next(inputfile)
            while line.strip():
                try:
                    temp = int(line[0:4])
                except ValueError:
                    pass
                else:
                    values.append([float(line.split()[self.scf_valcol])])
                line = next(inputfile)
            self.scfvalues.append(values)

        # Extract normal coordinate analysis, including vibrational frequencies (vibfreq),
        # IT intensities (vibirs) and displacements (vibdisps).
        #
        # This section typically looks like the following in GAMESS-US:
        #
        # MODES 1 TO 6 ARE TAKEN AS ROTATIONS AND TRANSLATIONS.
        #
        #     FREQUENCIES IN CM**-1, IR INTENSITIES IN DEBYE**2/AMU-ANGSTROM**2,
        #     REDUCED MASSES IN AMU.
        #
        #                          1           2           3           4           5
        #       FREQUENCY:        52.49       41.45       17.61        9.23       10.61
        #    REDUCED MASS:      3.92418     3.77048     5.43419     6.44636     5.50693
        #    IR INTENSITY:      0.00013     0.00001     0.00004     0.00000     0.00003
        #
        # ...or in the case of a numerical Hessian job...
        #
        # MODES 1 TO 5 ARE TAKEN AS ROTATIONS AND TRANSLATIONS.
        #
        #     FREQUENCIES IN CM**-1, IR INTENSITIES IN DEBYE**2/AMU-ANGSTROM**2,
        #     REDUCED MASSES IN AMU.
        #
        #                          1           2           3           4           5
        #       FREQUENCY:         0.05        0.03        0.03       30.89       30.94
        #    REDUCED MASS:      8.50125     8.50137     8.50136     1.06709     1.06709
        #
        # ...whereas PC-GAMESS has...
        #
        # MODES 1 TO 6 ARE TAKEN AS ROTATIONS AND TRANSLATIONS.
        #
        #     FREQUENCIES IN CM**-1, IR INTENSITIES IN DEBYE**2/AMU-ANGSTROM**2
        #
        #                          1           2           3           4           5
        #       FREQUENCY:         5.89        1.46        0.01        0.01        0.01
        #    IR INTENSITY:      0.00000     0.00000     0.00000     0.00000     0.00000
        #
        # If Raman is present we have (for PC-GAMESS)...
        #
        # MODES 1 TO 6 ARE TAKEN AS ROTATIONS AND TRANSLATIONS.
        #
        #     FREQUENCIES IN CM**-1, IR INTENSITIES IN DEBYE**2/AMU-ANGSTROM**2
        #     RAMAN ACTIVITIES IN ANGSTROM**4/AMU, DEPOLARIZATIONS ARE DIMENSIONLESS
        #
        #                          1           2           3           4           5
        #       FREQUENCY:         5.89        1.46        0.04        0.03        0.01
        #    IR INTENSITY:      0.00000     0.00000     0.00000     0.00000     0.00000
        # RAMAN ACTIVITY:       12.675       1.828       0.000       0.000       0.000
        #  DEPOLARIZATION:        0.750       0.750       0.124       0.009       0.750
        #
        # If GAMESS-US or PC-GAMESS has not reached the stationary point we have
        # and additional warning, repeated twice, like so (see n_water.log for an example):
        #
        #     *******************************************************
        #     * THIS IS NOT A STATIONARY POINT ON THE MOLECULAR PES *
        #     *     THE VIBRATIONAL ANALYSIS IS NOT VALID !!!       *
        #     *******************************************************
        #
        # There can also be additional warnings about the selection of modes, for example:
        #
        # * * * WARNING, MODE 6 HAS BEEN CHOSEN AS A VIBRATION
        #          WHILE MODE12 IS ASSUMED TO BE A TRANSLATION/ROTATION.
        # PLEASE VERIFY THE PROGRAM'S DECISION MANUALLY!
        #
        if "NORMAL COORDINATE ANALYSIS IN THE HARMONIC APPROXIMATION" in line:
            self.vibfreqs = []
            self.vibirs = []
            self.vibdisps = []

            # Need to get to the modes line, which is often preceeded by
            # a list of atomic weights and some possible warnings.
            # Pass the warnings to the logger if they are there.
            while "MODES" not in line:
                self.updateprogress(inputfile, "Frequency Information")

                line = next(inputfile)

                # Typical Atomic Masses section printed in GAMESS
                #               ATOMIC WEIGHTS (AMU)
                #
                # 1     O                15.99491
                # 2     H                 1.00782
                # 3     H                 1.00782
                if "ATOMIC WEIGHTS" in line:
                    atommasses = []
                    self.skip_line(inputfile, ["b"])
                    # There is a blank line after ATOMIC WEIGHTS
                    line = next(inputfile)
                    while line.strip():
                        temp = line.strip().split()
                        atommasses.append(float(temp[2]))
                        line = next(inputfile)
                    self.set_attribute("atommasses", atommasses)

                if "THIS IS NOT A STATIONARY POINT" in line:
                    self.logger.warning(
                        "\n   This is not a stationary point on the molecular PES"
                        "\n   The vibrational analysis is not valid!!!"
                    )
                if "* * * WARNING, MODE" in line:
                    line1 = line.strip()
                    line2 = next(inputfile).strip()
                    line3 = next(inputfile).strip()
                    self.logger.warning("\n   " + "\n   ".join((line1, line2, line3)))

            # In at least one case (regression zolm_dft3a.log) for older version of GAMESS-US,
            # the header concerning the range of nodes is formatted wrong and can look like so:
            # MODES 9 TO14 ARE TAKEN AS ROTATIONS AND TRANSLATIONS.
            #  ... although it's unclear whether this happens for all two-digit values.
            startrot = int(line.split()[1])
            if len(line.split()[2]) == 2:
                endrot = int(line.split()[3])
            else:
                endrot = int(line.split()[2][2:])

            self.skip_line(inputfile, "blank")

            # Continue down to the first frequencies
            line = next(inputfile)
            # With GAMESS-US 20 APR 2017 (R1), there are 28 blank spaces,
            # in earlier versions there used to be 26.
            while not line.strip() or not re.search(" {26,}1", line) is not None:
                line = next(inputfile)

            while "SAYVETZ" not in line:
                self.updateprogress(inputfile, "Frequency Information")

                # Note: there may be imaginary frequencies like this (which we make negative):
                #       FREQUENCY:       825.18 I    111.53       12.62       10.70        0.89
                #
                # A note for debuggers: some of these frequencies will be removed later,
                # assumed to be translations or rotations (see startrot/endrot above).
                for col in next(inputfile).split()[1:]:
                    if col == "I":
                        self.vibfreqs[-1] *= -1
                    else:
                        self.vibfreqs.append(float(col))

                line = next(inputfile)

                # Skip the symmetry (appears in newer versions), fixes bug #3476063.
                if line.find("SYMMETRY") >= 0:
                    line = next(inputfile)

                # Skip the reduced mass (not always present).
                if line.find("REDUCED") >= 0:
                    if not hasattr(self, "vibrmasses"):
                        self.vibrmasses = []
                    self.vibrmasses.extend(list(map(float, line.strip().split()[2:])))
                    line = next(inputfile)

                # Not present in numerical Hessian calculations.
                if line.find("IR INTENSITY") >= 0:
                    irIntensity = map(float, line.strip().split()[2:])
                    self.vibirs.extend(
                        [
                            utils.convertor(x, "Debye^2/amu-Angstrom^2", "km/mol")
                            for x in irIntensity
                        ]
                    )
                    line = next(inputfile)

                # Read in Raman vibrational intensities if present.
                if line.find("RAMAN") >= 0:
                    if not hasattr(self, "vibramans"):
                        self.vibramans = []
                    ramanIntensity = line.strip().split()
                    self.vibramans.extend(list(map(float, ramanIntensity[2:])))
                    depolar = next(inputfile)  # noqa: F841
                    line = next(inputfile)

                # This line seems always to be blank.
                assert line.strip() == ""

                # Extract the Cartesian displacement vectors.
                p = [[], [], [], [], []]
                for j in range(self.natom):
                    q = [[], [], [], [], []]
                    for coord in "xyz":
                        line = next(inputfile)[21:]
                        cols = list(map(float, line.split()))
                        for i, val in enumerate(cols):
                            q[i].append(val)
                    for k in range(len(cols)):
                        p[k].append(q[k])
                self.vibdisps.extend(p[: len(cols)])

                # Skip the Sayvetz stuff at the end.
                for j in range(10):
                    line = next(inputfile)

                self.skip_line(inputfile, "blank")
                line = next(inputfile)

            # Exclude rotations and translations.
            self.vibfreqs = numpy.array(self.vibfreqs[: startrot - 1] + self.vibfreqs[endrot:], "d")
            self.vibirs = numpy.array(self.vibirs[: startrot - 1] + self.vibirs[endrot:], "d")
            self.vibdisps = numpy.array(self.vibdisps[: startrot - 1] + self.vibdisps[endrot:], "d")
            if hasattr(self, "vibrmasses"):
                self.vibrmasses = numpy.array(
                    self.vibrmasses[: startrot - 1] + self.vibrmasses[endrot:], "d"
                )
            if hasattr(self, "vibramans"):
                self.vibramans = numpy.array(
                    self.vibramans[: startrot - 1] + self.vibramans[endrot:], "d"
                )

        if line[5:21] == "ATOMIC BASIS SET":
            self.gbasis = []
            line = next(inputfile)
            while line.find("SHELL") < 0:
                line = next(inputfile)

            self.skip_lines(inputfile, ["blank", "atomname"])

            # shellcounter stores the shell no of the last shell
            # in the previous set of primitives
            shellcounter = 1
            while line.find("TOTAL NUMBER") < 0:
                self.skip_line(inputfile, "blank")

                line = next(inputfile)
                shellno = int(line.split()[0])
                shellgap = shellno - shellcounter
                gbasis = []  # Stores basis sets on one atom
                shellsize = 0
                while len(line.split()) != 1 and line.find("TOTAL NUMBER") < 0:
                    shellsize += 1
                    coeff = {}
                    # coefficients and symmetries for a block of rows
                    while line.strip():
                        temp = line.strip().split()
                        sym = temp[1]
                        assert sym in ["S", "P", "D", "F", "G", "L"]
                        if sym == "L":  # L refers to SP
                            if len(temp) == 6:  # GAMESS US
                                coeff.setdefault("S", []).append((float(temp[3]), float(temp[4])))
                                coeff.setdefault("P", []).append((float(temp[3]), float(temp[5])))
                            else:  # PC GAMESS
                                assert temp[6][-1] == temp[9][-1] == ")"
                                coeff.setdefault("S", []).append(
                                    (float(temp[3]), float(temp[6][:-1]))
                                )
                                coeff.setdefault("P", []).append(
                                    (float(temp[3]), float(temp[9][:-1]))
                                )
                        else:
                            if len(temp) == 5:  # GAMESS US
                                coeff.setdefault(sym, []).append((float(temp[3]), float(temp[4])))
                            else:  # PC GAMESS
                                assert temp[6][-1] == ")"
                                coeff.setdefault(sym, []).append(
                                    (float(temp[3]), float(temp[6][:-1]))
                                )
                        line = next(inputfile)
                    # either a blank or a continuation of the block
                    if sym == "L":
                        gbasis.append(("S", coeff["S"]))
                        gbasis.append(("P", coeff["P"]))
                    else:
                        gbasis.append((sym, coeff[sym]))
                    line = next(inputfile)
                # either the start of the next block or the start of a new atom or
                # the end of the basis function section

                numtoadd = 1 + (shellgap // shellsize)
                shellcounter = shellno + shellsize
                for x in range(numtoadd):
                    self.gbasis.append(gbasis)

        # The eigenvectors, which also include MO energies and symmetries, follow
        # the *final* report of evalues and the last list of symmetries in the log file:
        #
        #           ------------
        #           EIGENVECTORS
        #           ------------
        #
        #                       1          2          3          4          5
        #                   -10.0162   -10.0161   -10.0039   -10.0039   -10.0029
        #                      BU         AG         BU         AG         AG
        #     1  C  1  S    0.699293   0.699290  -0.027566   0.027799   0.002412
        #     2  C  1  S    0.031569   0.031361   0.004097  -0.004054  -0.000605
        #     3  C  1  X    0.000908   0.000632  -0.004163   0.004132   0.000619
        #     4  C  1  Y   -0.000019   0.000033   0.000668  -0.000651   0.005256
        #     5  C  1  Z    0.000000   0.000000   0.000000   0.000000   0.000000
        #     6  C  2  S   -0.699293   0.699290   0.027566   0.027799   0.002412
        #     7  C  2  S   -0.031569   0.031361  -0.004097  -0.004054  -0.000605
        #     8  C  2  X    0.000908  -0.000632  -0.004163  -0.004132  -0.000619
        #     9  C  2  Y   -0.000019  -0.000033   0.000668   0.000651  -0.005256
        #    10  C  2  Z    0.000000   0.000000   0.000000   0.000000   0.000000
        #    11  C  3  S   -0.018967  -0.019439   0.011799  -0.014884  -0.452328
        #    12  C  3  S   -0.007748  -0.006932   0.000680  -0.000695  -0.024917
        #    13  C  3  X    0.002628   0.002997   0.000018   0.000061  -0.003608
        # ...
        #
        # There are blanks lines between each block.
        #
        # Warning! There are subtle differences between GAMESS-US and PC-GAMES
        # in the formatting of the first four columns. In particular, for F orbitals,
        # PC GAMESS:
        #   19  C   1 YZ   0.000000   0.000000   0.000000   0.000000   0.000000
        #   20  C    XXX   0.000000   0.000000   0.000000   0.000000   0.002249
        #   21  C    YYY   0.000000   0.000000  -0.025555   0.000000   0.000000
        #   22  C    ZZZ   0.000000   0.000000   0.000000   0.002249   0.000000
        #   23  C    XXY   0.000000   0.000000   0.001343   0.000000   0.000000
        # GAMESS US
        #   55  C  1 XYZ   0.000000   0.000000   0.000000   0.000000   0.000000
        #   56  C  1XXXX  -0.000014  -0.000067   0.000000   0.000000   0.000000
        #
        if (
            line.find("EIGENVECTORS") == 10
            or line.find("MOLECULAR ORBITALS") == 10
            or line.find("INITIAL GUESS ORBITALS") == 30
        ):
            # This is the stuff that we can read from these blocks.
            self.moenergies = [[]]
            self.mosyms = [[]]

            if not hasattr(self, "nmo"):
                self.nmo = self.nbasis

            self.mocoeffs = [numpy.zeros((self.nmo, self.nbasis), "d")]

            readatombasis = False
            if not hasattr(self, "atombasis"):
                self.atombasis = []
                self.aonames = []
                for _ in range(self.natom):
                    self.atombasis.append([])
                self.aonames = []
                readatombasis = True

            self.skip_line(inputfile, "dashes")

            for base in range(0, self.nmo, 5):
                self.updateprogress(inputfile, "Coefficients")

                line = next(inputfile)

                # This makes sure that this section does not end prematurely,
                # which happens in regression 2CO.ccsd.aug-cc-pVDZ.out.
                if line.strip() != "":
                    break

                numbers = next(inputfile)  # Eigenvector numbers.

                # This is for regression CdtetraM1B3LYP.
                if "ALPHA SET" in numbers:
                    self.skip_line(inputfile, "b")
                    numbers = next(inputfile)

                # If not all coefficients are printed, the logfile will go right to
                # the beta section if there is one, so break out in that case.
                if "BETA SET" in numbers:
                    line = numbers
                    break

                # Sometimes there are some blank lines here.
                while not line.strip():
                    line = next(inputfile)

                # Geometry optimizations don't have END OF RHF/DFT
                # CALCULATION, they head right into the next section.
                if "--------" in line:
                    break

                # Eigenvalues for these orbitals (in hartrees).
                try:
                    self.moenergies[0].extend([float(x) for x in line.split()])
                except:  # noqa: E722
                    self.logger.warning("MO section found but could not be parsed!")
                    break

                # Orbital symmetries.
                line = next(inputfile)
                if line.strip():
                    self.mosyms[0].extend(list(map(self.normalisesym, line.split())))

                # Now we have nbasis lines. We will use the same method as in normalise_aonames() before.
                p = re.compile(r"(\d+)\s*([A-Z][A-Z]?)\s*(\d+)\s*([A-Z]+)")
                oldatom = "0"
                i_atom = 0  # counter to keep track of n_atoms > 99
                flag_w = True  # flag necessary to keep from adding 100's at wrong time

                for i in range(self.nbasis):
                    line = next(inputfile)

                    # If line is empty, break (ex. for FMO in exam37 which is a regression).
                    if not line.strip():
                        break

                    # Fill atombasis and aonames only first time around
                    if readatombasis and base == 0:
                        start = line[:17].strip()
                        m = p.search(start)

                        if m:
                            g = m.groups()
                            g2 = int(g[2])  # atom index in GAMESS file; changes to 0 after 99

                            # Check if we have moved to a hundred
                            # if so, increment the counter and add it to the parsed value
                            # There will be subsequent 0's as that atoms AO's are parsed
                            # so wait until the next atom is parsed before resetting flag
                            if g2 == 0 and flag_w:
                                i_atom = i_atom + 100
                                flag_w = False  # handle subsequent AO's
                            if g2 != 0:
                                flag_w = True  # reset flag
                            g2 = g2 + i_atom

                            aoname = f"{g[1].capitalize()}{int(g2)}_{g[3]}"
                            oldatom = str(g2)
                            atomno = g2 - 1
                            orbno = int(g[0]) - 1
                        else:  # For F orbitals, as shown above
                            g = [x.strip() for x in line.split()]
                            aoname = f"{g[1].capitalize()}{oldatom}_{g[2]}"
                            atomno = int(oldatom) - 1
                            orbno = int(g[0]) - 1

                        self.atombasis[atomno].append(orbno)
                        self.aonames.append(aoname)

                    coeffs = line[15:]  # Strip off the crud at the start.
                    j = 0
                    while j * 11 + 4 < len(coeffs):
                        self.mocoeffs[0][base + j, i] = float(coeffs[j * 11 : (j + 1) * 11])
                        j += 1

            # If it's a restricted calc and no more properties, we have:
            #
            #  ...... END OF RHF/DFT CALCULATION ......
            #
            # If there are more properties (such as the density matrix):
            #               --------------
            #
            # If it's an unrestricted calculation, however, we now get the beta orbitals:
            #
            #  ----- BETA SET -----
            #
            #          ------------
            #          EIGENVECTORS
            #          ------------
            #
            #                      1          2          3          4          5
            # ...
            #
            if "BETA SET" not in line:
                line = next(inputfile)
                line = next(inputfile)

            # This can come in between the alpha and beta orbitals (see #130).
            if line.strip() == "LZ VALUE ANALYSIS FOR THE MOS":
                while line.strip():
                    line = next(inputfile)
                line = next(inputfile)

            # Covers label with both dashes and stars (like regression CdtetraM1B3LYP).
            if "BETA SET" in line:
                self.append_attribute("mocoeffs", numpy.zeros((self.nmo, self.nbasis), "d"))
                self.append_attribute("moenergies", [])
                self.append_attribute("mosyms", [])
                self.skip_line(inputfile, "b")
                line = next(inputfile)

                # Sometimes EIGENVECTORS is missing, so rely on dashes to signal it.
                if set(line.strip()) == {"-"}:
                    self.skip_lines(inputfile, ["EIGENVECTORS", "d", "b"])
                    line = next(inputfile)

                for base in range(0, self.nmo, 5):
                    self.updateprogress(inputfile, "Coefficients")
                    if base != 0:
                        line = next(inputfile)
                        line = next(inputfile)
                    line = next(inputfile)
                    if "properties" in line.lower():
                        break
                    self.moenergies[1].extend([float(x) for x in line.split()])
                    line = next(inputfile)
                    self.mosyms[1].extend(list(map(self.normalisesym, line.split())))
                    for i in range(self.nbasis):
                        line = next(inputfile)
                        temp = line[15:]  # Strip off the crud at the start
                        j = 0
                        while j * 11 + 4 < len(temp):
                            self.mocoeffs[1][base + j, i] = float(temp[j * 11 : (j + 1) * 11])
                            j += 1
                line = next(inputfile)
            self.moenergies = [numpy.array(x, "d") for x in self.moenergies]

        # Natural orbital coefficients and occupation numbers, presently supported only
        # for CIS calculations. Looks the same as eigenvectors, without symmetry labels.
        #
        #          --------------------
        #          CIS NATURAL ORBITALS
        #          --------------------
        #
        #                      1          2          3          4          5
        #
        #                    2.0158     2.0036     2.0000     2.0000     1.0000
        #
        #    1  O  1  S    0.000000  -0.157316   0.999428   0.164938   0.000000
        #    2  O  1  S    0.000000   0.754402   0.004472  -0.581970   0.000000
        # ...
        #
        if (
            line[10:30] == "CIS NATURAL ORBITALS"
            or line[10:50] == "NATURAL ORBITALS IN ATOMIC ORBITAL BASIS"
        ):
            self.nocoeffs = numpy.zeros((self.nmo, self.nbasis), "d")
            self.nooccnos = []

            self.skip_line(inputfile, "dashes")

            for base in range(0, self.nmo, 5):
                self.skip_lines(inputfile, ["blank", "numbers"])

                # The eigenvalues that go along with these natural orbitals are
                # their occupation numbers. Sometimes there are blank lines before them.
                line = next(inputfile)
                while not line.strip():
                    line = next(inputfile)
                eigenvalues = map(float, line.split())
                self.nooccnos.extend(eigenvalues)

                # Orbital symemtry labels are normally here for MO coefficients.
                line = next(inputfile)

                # Now we have nbasis lines with the coefficients.
                for i in range(self.nbasis):
                    line = next(inputfile)
                    coeffs = line[15:]
                    j = 0
                    while j * 11 + 4 < len(coeffs):
                        self.nocoeffs[base + j, i] = float(coeffs[j * 11 : (j + 1) * 11])
                        j += 1

        # We cannot trust this self.homos until we come to the phrase:
        #   SYMMETRIES FOR INITAL GUESS ORBITALS FOLLOW
        # which either is followed by "ALPHA" or "BOTH" at which point we can say
        # for certain that it is an un/restricted calculations.
        # Note that MCSCF calcs also print this search string, so make sure
        #   that self.homos does not exist yet.
        if line[1:28] == "NUMBER OF OCCUPIED ORBITALS" and not hasattr(self, "homos"):
            homos = [int(line.split()[-1]) - 1]
            line = next(inputfile)
            homos.append(int(line.split()[-1]) - 1)

            self.set_attribute("homos", homos)

        if line.find("SYMMETRIES FOR INITIAL GUESS ORBITALS FOLLOW") >= 0:
            # Not unrestricted, so lop off the second index.
            # In case the search string above was not used (ex. FMO in exam38),
            #   we can try to use the next line which should also contain the
            #   number of occupied orbitals.
            if line.find("BOTH SET(S)") >= 0:
                nextline = next(inputfile)
                if "ORBITALS ARE OCCUPIED" in nextline:
                    homos = int(nextline.split()[0]) - 1
                    if hasattr(self, "homos"):
                        try:
                            assert self.homos[0] == homos
                        except AssertionError:
                            self.logger.warning(
                                "Number of occupied orbitals not consistent. This is normal for ECP and FMO jobs."
                            )
                    else:
                        self.homos = [homos]
                self.homos = numpy.resize(self.homos, [1])

        # Set the total number of atoms, only once.
        # Normally GAMESS print TOTAL NUMBER OF ATOMS, however in some cases
        #   this is slightly different (ex. lower case for FMO in exam37).
        if not hasattr(self, "natom") and "NUMBER OF ATOMS" in line.upper():
            natom = int(line.split()[-1])
            self.set_attribute("natom", natom)

        # The first is from Julien's Example and the second is from Alexander's
        # I think it happens if you use a polar basis function instead of a cartesian one
        if (
            line.find("NUMBER OF CARTESIAN GAUSSIAN BASIS") == 1
            or line.find("TOTAL NUMBER OF BASIS FUNCTIONS") == 1
        ):
            nbasis = int(line.strip().split()[-1])
            self.set_attribute("nbasis", nbasis)

        elif line.find("TOTAL NUMBER OF CONTAMINANTS DROPPED") >= 0:
            nmos_dropped = int(line.split()[-1])
            if hasattr(self, "nmo"):
                self.set_attribute("nmo", self.nmo - nmos_dropped)
            else:
                self.set_attribute("nmo", self.nbasis - nmos_dropped)

        # Note that this line is present if ISPHER=1, e.g. for C_bigbasis
        elif line.find("SPHERICAL HARMONICS KEPT IN THE VARIATION SPACE") >= 0:
            nmo = int(line.strip().split()[-1])
            self.set_attribute("nmo", nmo)

        # Note that this line is not always present, so by default
        # NBsUse is set equal to NBasis (see below).
        elif line.find("TOTAL NUMBER OF MOS IN VARIATION SPACE") == 1:
            nmo = int(line.split()[-1])
            self.set_attribute("nmo", nmo)

        elif line.find("OVERLAP MATRIX") == 0 or line.find("OVERLAP MATRIX") == 1:
            # The first is for PC-GAMESS, the second for GAMESS
            # Read 1-electron overlap matrix
            if not hasattr(self, "aooverlaps"):
                self.aooverlaps = numpy.zeros((self.nbasis, self.nbasis), "d")
            else:
                self.logger.info("Reading additional aooverlaps...")
            base = 0
            while base < self.nbasis:
                self.updateprogress(inputfile, "Overlap")

                self.skip_lines(inputfile, ["b", "basis_fn_number", "b"])

                for i in range(self.nbasis - base):  # Fewer lines each time
                    line = next(inputfile)
                    ovlp_line = line.split()
                    # handle case of merged columns of two-character symbol and index
                    if len(ovlp_line[1]) == 4:
                        element = ovlp_line[1][0:2]
                        number = ovlp_line[1][2:]
                        ovlp_line[1] = element
                        ovlp_line.insert(2, number)
                    for j in range(4, len(ovlp_line)):
                        self.aooverlaps[base + j - 4, i + base] = float(ovlp_line[j])
                        self.aooverlaps[i + base, base + j - 4] = float(ovlp_line[j])
                base += 5

        # ECP Pseudopotential information
        if "ECP POTENTIALS" in line:
            if not hasattr(self, "coreelectrons"):
                self.coreelectrons = [0] * self.natom

            self.skip_lines(inputfile, ["d", "b"])

            header = next(inputfile)
            while header.split()[0] == "PARAMETERS":
                element_symbol_dash_ecp = header[17:25]  # noqa: F841
                atomnum = int(header[34:40])
                # The pseudopotential is given explicitly
                if header[40:50] == "WITH ZCORE":
                    zcore = int(header[50:55])
                    lmax = int(header[63:67])  # noqa: F841
                    self.coreelectrons[atomnum - 1] = zcore
                # The pseudopotential is copied from another atom
                elif header[40:55] == "ARE THE SAME AS":
                    atomcopy = int(header[60:])
                    self.coreelectrons[atomnum - 1] = self.coreelectrons[atomcopy - 1]
                line = next(inputfile)
                while line.split() != []:
                    line = next(inputfile)
                header = next(inputfile)

        # This was used before refactoring the parser, geotargets was set here after parsing.
        # if not hasattr(self, "geotargets"):
        #    opttol = 1e-4
        #    self.geotargets = numpy.array([opttol, 3. / opttol], "d")
        # if hasattr(self,"geovalues"): self.geovalues = numpy.array(self.geovalues, "d")

        # This is quite simple to parse, but some files seem to print certain lines twice,
        # repeating the populations without charges, but not in proper order.
        # The unrestricted calculations are a bit tricky, since GAMESS-US prints populations
        # for both alpha and beta orbitals in the same format and with the same title,
        # but it still prints the charges only at the very end.
        if "TOTAL MULLIKEN AND LOWDIN ATOMIC POPULATIONS" in line:
            if not hasattr(self, "atomcharges"):
                self.atomcharges = {}

            header = next(inputfile)
            line = next(inputfile)

            # It seems that when population are printed twice (without charges),
            # there is a blank line along the way (after the first header),
            # so let's get a flag out of that circumstance.
            doubles_printed = line.strip() == ""
            if doubles_printed:
                self.skip_line(inputfile, "TOTAL MULLIKEN AND LOWDIN ATOMIC POPULATIONS")
                header = next(inputfile)
                line = next(inputfile)

            # Only go further if the header had five columns, which should
            # be the case when both populations and charges are printed.
            # This is pertinent for both double printing and unrestricted output.
            if not len(header.split()) == 5:
                return
            mulliken, lowdin = [], []
            while line.strip():
                if line.strip() and doubles_printed:
                    line = next(inputfile)
                mulliken.append(float(line.split()[3]))
                lowdin.append(float(line.split()[5]))
                line = next(inputfile)
            self.atomcharges["mulliken"] = mulliken
            self.atomcharges["lowdin"] = lowdin

        #          ---------------------
        #          ELECTROSTATIC MOMENTS
        #          ---------------------
        #
        # POINT   1           X           Y           Z (BOHR)    CHARGE
        #                -0.000000    0.000000    0.000000       -0.00 (A.U.)
        #         DX          DY          DZ         /D/  (DEBYE)
        #     0.000000   -0.000000    0.000000    0.000000
        #
        if line.strip() == "ELECTROSTATIC MOMENTS":
            self.skip_lines(inputfile, ["d", "b"])
            line = next(inputfile)

            # The old PC-GAMESS prints memory assignment information here.
            if "MEMORY ASSIGNMENT" in line:
                self.skip_line(inputfile, "IELM IEMW IDENSA IDENSB LAST")
                line = next(inputfile)

            # If something else ever comes up, we should get a signal from this assert.
            assert line.split()[0] == "POINT"

            # We can get the reference point from here, as well as
            # check here that the net charge of the molecule is correct.
            coords_and_charge = next(inputfile)
            assert coords_and_charge.split()[-1] == "(A.U.)"
            reference = numpy.array([float(x) for x in coords_and_charge.split()[:3]])
            reference = utils.convertor(reference, "bohr", "Angstrom")
            charge = int(round(float(coords_and_charge.split()[-2])))
            self.set_attribute("charge", charge)

            dipoleheader = next(inputfile)
            assert dipoleheader.split()[:3] == ["DX", "DY", "DZ"]
            assert dipoleheader.split()[-1] == "(DEBYE)"

            dipoleline = next(inputfile)
            dipole = [float(d) for d in dipoleline.split()[:3]]

            # The dipole is always the first multipole moment to be printed,
            # so if it already exists, we will overwrite all moments since we want
            # to leave just the last printed value (could change in the future).
            if not hasattr(self, "moments"):
                self.moments = [reference, dipole]
            else:
                try:
                    assert self.moments[1] == dipole
                except AssertionError:
                    self.logger.warning(
                        "Overwriting previous multipole moments with new values; "
                        "This could be from post-HF properties or geometry optimization"
                    )
                    self.set_attribute("moments", [reference, dipole])

        # Static polarizability from a harmonic frequency calculation
        # with $CPHF/POLAR=.TRUE.
        if line.strip() == "ALPHA POLARIZABILITY TENSOR (ANGSTROMS**3)":
            if not hasattr(self, "polarizabilities"):
                self.polarizabilities = []
            polarizability = numpy.zeros(shape=(3, 3))
            self.skip_lines(inputfile, ["d", "b", "directions"])
            for i in range(3):
                line = next(inputfile)
                polarizability[i, : i + 1] = [float(x) for x in line.split()[1:]]
            polarizability = utils.symmetrize(polarizability, use_triangle="lower")
            # Convert from Angstrom**3 to bohr**3 (a.u.**3).
            volume_convert = numpy.vectorize(
                lambda x: x * utils.convertor(1, "Angstrom", "bohr") ** 3
            )
            polarizability = volume_convert(polarizability)
            self.polarizabilities.append(polarizability)

        # Static and dynamic polarizability from RUNTYP=TDHF.
        if line.strip() == "TIME-DEPENDENT HARTREE-FOCK NLO PROPERTIES":
            if not hasattr(self, "polarizabilities"):
                self.polarizabilities = []
            polarizability = numpy.empty(shape=(3, 3))
            coord_to_idx = {"X": 0, "Y": 1, "Z": 2}
            self.skip_lines(inputfile, ["d", "b", "dots"])
            line = next(inputfile)
            assert "ALPHA AT" in line
            self.skip_lines(inputfile, ["dots", "b"])
            for a in range(3):
                for b in range(3):
                    line = next(inputfile)
                    tokens = line.split()
                    i, j = coord_to_idx[tokens[1][0]], coord_to_idx[tokens[1][1]]
                    polarizability[i, j] = tokens[3]
            self.polarizabilities.append(polarizability)

        # Extract thermochemistry

        #      -------------------------------
        #      THERMOCHEMISTRY AT T=  298.15 K
        #      -------------------------------

        #  USING IDEAL GAS, RIGID ROTOR, HARMONIC NORMAL MODE APPROXIMATIONS.
        #  P=  1.01325E+05 PASCAL.
        #  ALL FREQUENCIES ARE SCALED BY   1.00000
        #  THE MOMENTS OF INERTIA ARE (IN AMU*BOHR**2)
        #               1.77267             4.73429             6.50696
        #  THE ROTATIONAL SYMMETRY NUMBER IS  1.0
        #  THE ROTATIONAL CONSTANTS ARE (IN GHZ)
        #    1017.15677   380.85747   277.10144
        #       7 -      9 VIBRATIONAL MODES ARE USED IN THERMOCHEMISTRY.
        #  THE HARMONIC ZERO POINT ENERGY IS (SCALED BY   1.000)
        #         0.020711 HARTREE/MOLECULE     4545.618665 CM**-1/MOLECULE
        #        12.996589 KCAL/MOL               54.377728 KJ/MOL

        #                Q               LN Q
        #  ELEC.     1.00000E+00       0.000000
        #  TRANS.    3.00431E+06      14.915558
        #  ROT.      8.36512E+01       4.426656
        #  VIB.      1.00067E+00       0.000665
        #  TOT.      2.51481E+08      19.342880

        #               E         H         G         CV        CP        S
        #            KJ/MOL    KJ/MOL    KJ/MOL   J/MOL-K   J/MOL-K   J/MOL-K
        #  ELEC.      0.000     0.000     0.000     0.000     0.000     0.000
        #  TRANS.     3.718     6.197   -36.975    12.472    20.786   144.800
        #  ROT.       3.718     3.718   -10.973    12.472    12.472    49.277
        #  VIB.      54.390    54.390    54.376     0.296     0.296     0.046
        #  TOTAL     61.827    64.306     6.428    25.240    33.554   194.123
        #  VIB. THERMAL CORRECTION E(T)-E(0) = H(T)-H(0) =        12.071 J/MOL

        #               E         H         G         CV        CP        S
        #          KCAL/MOL  KCAL/MOL  KCAL/MOL CAL/MOL-K CAL/MOL-K CAL/MOL-K
        #  ELEC.      0.000     0.000     0.000     0.000     0.000     0.000
        #  TRANS.     0.889     1.481    -8.837     2.981     4.968    34.608
        #  ROT.       0.889     0.889    -2.623     2.981     2.981    11.777
        #  VIB.      12.999    12.999    12.996     0.071     0.071     0.011
        #  TOTAL     14.777    15.369     1.536     6.032     8.020    46.396
        #  VIB. THERMAL CORRECTION E(T)-E(0) = H(T)-H(0) =         2.885 CAL/MOL

        if "THERMOCHEMISTRY AT T=" in line:
            match = re.search(r"THERMOCHEMISTRY AT T=(.*)K", line)
            if match:
                self.set_attribute("temperature", float(match.group(1)))
            self.skip_lines(inputfile, ["d", "b", "USING IDEAL GAS, ..."])
            line = next(inputfile)
            assert "PASCAL." in line
            match = re.search(r"P=(.*)PASCAL.", line)
            if match:
                self.set_attribute("pressure", float(match.group(1)) / 1.01325e5)
            lines = self.skip_lines(
                inputfile,
                [
                    "ALL FREQUENCIES ARE SCALED",
                    "THE MOMENTS OF INERTIA ARE (IN AMU*BOHR**2)",
                    "moments of inertia",
                    "THE ROTATIONAL SYMMETRY NUMBER IS",
                    "THE ROTATIONAL CONSTANTS ARE (IN GHZ)",
                ],
            )
            line = next(inputfile)
            self.append_attribute("rotconsts", [float(x) for x in line.split()])
            # Sometimes the volume is printed between the pressure and "ALL
            # FREQUENCIES ARE SCALED".
            if lines[0][:3] == " V=":
                line = next(inputfile)
            line = next(inputfile)
            if "IMAGINARY FREQUENCY VIBRATION(S)" in line:
                line = next(inputfile)
                line = next(inputfile)
            if "VIBRATIONAL MODES ARE USED IN THERMOCHEMISTRY." in line:
                line = next(inputfile)
            line = next(inputfile)
            assert "HARTREE/MOLECULE" in line
            self.set_attribute("zpve", float(line.split()[0]))

        if line.strip() == "CARTESIAN FORCE CONSTANT MATRIX":
            natom = self.natom
            hessian = numpy.zeros((3 * natom, 3 * natom))
            field_width = 9
            starts = [20 + i * field_width for i in range(6)]
            self.skip_line(inputfile, "d")
            mode_count = 0
            nmodes_per_block = 2
            while mode_count < natom:
                lines = self.skip_lines(
                    inputfile, ["b", "atom indices", "atom symbols", "XYZ header"]
                )
                # An odd number of atoms will lead to the final part having
                # one column instead of two; handle it dynamically.
                if len(lines[1].split()) == 1:
                    starts = starts[:3]
                mode_count += nmodes_per_block
                imode_start = mode_count - nmodes_per_block
                for iatom_remaining in range(mode_count - nmodes_per_block, natom):
                    for icart in range(3):
                        line = next(inputfile)
                        hessian[
                            iatom_remaining * 3 + icart, imode_start : imode_start + len(starts)
                        ] = [float(line[start : start + field_width]) for start in starts]
            self.set_attribute("hessian", utils.symmetrize(hessian))

        if "KCAL/MOL  KCAL/MOL  KCAL/MOL CAL/MOL-K CAL/MOL-K CAL/MOL-K" in line:
            self.skip_lines(inputfile, ["ELEC", "TRANS", "ROT", "VIB"])
            line = next(inputfile)  # TOTAL
            thermoValues = line.split()

            electronic_energy = self.scfenergies[0]
            self.set_attribute(
                "enthalpy",
                electronic_energy + utils.convertor(float(thermoValues[2]), "kcal/mol", "hartree"),
            )
            self.set_attribute(
                "freeenergy",
                electronic_energy + utils.convertor(float(thermoValues[3]), "kcal/mol", "hartree"),
            )
            self.set_attribute(
                "entropy", utils.convertor(float(thermoValues[6]) / 1000.0, "kcal/mol", "hartree")
            )

        if (
            line[:30] == " ddikick.x: exited gracefully."
            or line[:41] == " EXECUTION OF FIREFLY TERMINATED NORMALLY"
            or line[:40] == " EXECUTION OF GAMESS TERMINATED NORMALLY"
        ):
            self.metadata["success"] = True
