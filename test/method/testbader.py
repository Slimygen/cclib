# Copyright (c) 2025, the cclib development team
#
# This file is part of cclib (http://cclib.github.io) and is distributed under
# the terms of the BSD 3-Clause License.

"""Test the various population analyses (MPA, LPA, CSPA, Bickelhaupt) in cclib"""

import os

from cclib.io import ccread
from cclib.method import Bader
from cclib.method.calculationmethod import MissingAttributeError
from cclib.method.volume import Volume, read_from_cube
from cclib.parser import Psi4

import numpy
import pytest
from numpy.testing import assert_allclose

from ..test_data import getdatafile


class BaderTest:
    """Bader's QTAIM method tests."""

    def testmissingrequiredattributes(self) -> None:
        """Is an error raised when required attributes are missing?"""
        for missing_attribute in Bader.required_attrs:
            data = parse()
            volume = Volume((-4, -4, -4), (4, 4, 4), (0.2, 0.2, 0.2))
            delattr(data, missing_attribute)
            with pytest.raises(MissingAttributeError):
                Bader(data, volume)

    def test_val(self) -> None:
        """Do the calculated values match with known values?"""

        data = parse()
        volume = Volume((-4, -4, -4), (4, 4, 4), (0.2, 0.2, 0.2))
        analysis = Bader(data, volume)
        analysis.calculate()

        ref_data = [6.9378, 0.3639, 0.3827]  # values from `bader` package

        assert_allclose(analysis.fragcharges, ref_data, atol=0.15)

    def test_chgsum_hf(self) -> None:
        """Does the sum of charges equate to the number of electrons for a simple molecule?"""

        hfpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "hf.out")
        data = ccread(hfpath)
        vol = Volume((-6, -6, -6), (6, 6, 6), (0.2, 0.2, 0.2))
        analysis = Bader(data, vol)
        analysis.calculate()

        assert abs(numpy.sum(analysis.fragcharges) - 10) < 1

    def test_symms_benzene(self) -> None:
        """Do the carbons in benzene ring get assigned with roughly equal charges?

        Discrepancy between carbons do exist in this test due to grid coarseness and limited
        size of the grid. One can do a larger test, for example, using 160x170x80 size grid to
        obtain [5.63728706, 5.89862956, 5.73956182, 5.63728706, 5.73963179, 5.8996759].
        In comparison, `bader`, which is implemented by Henkelman group which proposed
        the algorithm, reports [5.947370, 6.032509, 5.873431, 5.947370, 5.873431, 6.033485].
        `bader` uses fuzzy boundaries which result in slightly higher carbon charges.
        """

        benzenepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "benzene.out")
        data = ccread(benzenepath)
        vol = read_from_cube(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "benzene.cube")
        )
        assert_allclose(vol.origin, numpy.array([-4.1805, -4.498006, -2.116709]), atol=1e-3)

        analysis = Bader(data, vol)
        analysis.calculate()

        assert abs(analysis.fragcharges[0:6].max() - analysis.fragcharges[0:6].min()) < 0.5


def parse():
    data, _ = getdatafile(Psi4, "basicPsi4-1.2.1", ["water_mp2.out"])
    return data
