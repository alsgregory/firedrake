import pytest
from firedrake import *
from tests.common import *


@pytest.fixture
def opc_quad():
    return TensorProductCell(interval, interval)


@pytest.fixture
def opc_hex():
    return TensorProductCell(quadrilateral, interval)


@pytest.mark.parametrize('degree', [1, 2])
def test_rtce_expansion(opc_quad, degree):
    actual = FiniteElement("RTCE", opc_quad, degree)

    C_elt = FiniteElement("CG", interval, degree)
    D_elt = FiniteElement("DG", interval, degree - 1)
    expected = HCurl(TensorProductElement(C_elt, D_elt)) + HCurl(TensorProductElement(D_elt, C_elt))
    assert expected == actual


@pytest.mark.parametrize('degree', [1, 2])
def test_rtcf_expansion(opc_quad, degree):
    actual = FiniteElement("RTCF", opc_quad, degree)

    C_elt = FiniteElement("CG", interval, degree)
    D_elt = FiniteElement("DG", interval, degree - 1)
    expected = HDiv(TensorProductElement(C_elt, D_elt)) + HDiv(TensorProductElement(D_elt, C_elt))
    assert expected == actual


@pytest.mark.parametrize('degree', [1, 2])
def test_nce_expansion(opc_hex, degree):
    actual = FiniteElement("NCE", opc_hex, degree)

    W0_h = FiniteElement("Q", quadrilateral, degree)
    W1_h = FiniteElement("RTCE", quadrilateral, degree)

    W0_v = FiniteElement("DG", interval, degree - 1)
    W1_v = FiniteElement("CG", interval, degree)

    expected = HCurl(TensorProductElement(W0_h, W0_v)) + HCurl(TensorProductElement(W1_h, W1_v))
    assert expected == actual


@pytest.mark.parametrize('degree', [1, 2])
def test_ncf_expansion(opc_hex, degree):
    actual = FiniteElement("NCF", opc_hex, degree)

    W0_h = FiniteElement("RTCF", quadrilateral, degree)
    W1_h = FiniteElement("DQ", quadrilateral, degree - 1)

    W0_v = FiniteElement("DG", interval, degree - 1)
    W1_v = FiniteElement("CG", interval, degree)

    expected = HDiv(TensorProductElement(W0_h, W0_v)) + HDiv(TensorProductElement(W1_h, W1_v))
    assert expected == actual


@pytest.mark.parametrize('base_cell', [interval, triangle])
@pytest.mark.parametrize('fs', ["CG", "DG"])
@pytest.mark.parametrize('degree', [1, 2])
def test_cg_dg_expansion(base_cell, fs, degree):
    cell = TensorProductCell(base_cell, interval)
    actual = FiniteElement(fs, cell, degree)

    expected = TensorProductElement(FiniteElement(fs, base_cell, degree),
                                   FiniteElement(fs, interval, degree),
                                   domain=cell)
    assert expected == actual


@pytest.mark.parametrize('base_cell', [interval, triangle])
@pytest.mark.parametrize('fs', ["CG", "DG"])
@pytest.mark.parametrize('degree', [1, 2])
def test_cg_dg_vector_expansion(base_cell, fs, degree):
    cell = TensorProductCell(base_cell, interval)
    actual = VectorElement(fs, cell, degree, dim=3)

    expected = TensorProductVectorElement(FiniteElement(fs, base_cell, degree),
                                         FiniteElement(fs, interval, degree),
                                         domain=cell, dim=3)
    assert expected == actual


@pytest.mark.parametrize(('base_mesh_thunk', 'fs', 'degree'),
                         [(lambda: UnitIntervalMesh(10), "CG", 1),
                          (lambda: UnitIntervalMesh(10), "CG", 2),
                          (lambda: UnitIntervalMesh(10), "DG", 1),
                          (lambda: UnitIntervalMesh(10), "DG", 2),
                          (lambda: UnitIntervalMesh(10), "RTCE", 1),
                          (lambda: UnitIntervalMesh(10), "RTCE", 2),
                          (lambda: UnitIntervalMesh(10), "RTCF", 1),
                          (lambda: UnitIntervalMesh(10), "RTCF", 2),
                          (lambda: UnitSquareMesh(10, 10), "CG", 1),
                          (lambda: UnitSquareMesh(10, 10), "CG", 2),
                          (lambda: UnitSquareMesh(10, 10), "DG", 1),
                          (lambda: UnitSquareMesh(10, 10), "DG", 2)])
def test_ufl_element_assembly(base_mesh_thunk, fs, degree):
    mesh = ExtrudedMesh(base_mesh_thunk(), 10)
    V = FunctionSpace(mesh, fs, degree)

    assert V.ufl_element() == FiniteElement(fs, mesh.ufl_domain(), degree)


@pytest.mark.parametrize(('base_mesh_thunk', 'fs', 'degree'),
                         [(lambda: UnitIntervalMesh(10), "CG", 1),
                          (lambda: UnitIntervalMesh(10), "CG", 2),
                          (lambda: UnitIntervalMesh(10), "DG", 1),
                          (lambda: UnitIntervalMesh(10), "DG", 2),
                          (lambda: UnitSquareMesh(10, 10), "CG", 1),
                          (lambda: UnitSquareMesh(10, 10), "CG", 2),
                          (lambda: UnitSquareMesh(10, 10), "DG", 1),
                          (lambda: UnitSquareMesh(10, 10), "DG", 2)])
def test_ufl_vector_element_assembly(base_mesh_thunk, fs, degree):
    mesh = ExtrudedMesh(base_mesh_thunk(), 10)
    V = VectorFunctionSpace(mesh, fs, degree, dim=3)

    assert V.ufl_element() == VectorElement(fs, mesh.ufl_domain(), degree, dim=3)

if __name__ == '__main__':
    import os
    pytest.main(os.path.abspath(__file__))
