
""" Test Case for Observation Operator (December 2015) """


from __future__ import division # Get proper divison
import numpy as np
from firedrake import *
import pytest

@pytest.mark.xfail(reason="Expected to fail. Waiting for missing functionality. Function @M")
def test_distance_function_nonperturbed(): # this should return 0 as distance from observations to function for arbitrary coordinate
    # Define function spaces and functions for the observation and function that distance is to be found
    n0=10
    N0=100
    Mesh=RectangleMesh(n0,n0,1,1,quadrilateral=False)
    ObsMesh=RectangleMesh(N0,N0,1,1,quadrilateral=False)
    V=FunctionSpace(Mesh,"DG",1)
    Y=FunctionSpace(ObsMesh,"DG",1)
    ex=Expression("sin(x[0]*2*amp)",amp=np.pi)
    y=Function(Y); y.interpolate(ex)
    f=Function(V); f.interpolate(ex)
    # Evaluate observations 
    coordinates=[]
    for i in range(3):
        coordinates.append(np.array([0.2*(i+1),0.2*(i+1)]))
    Observations=np.zeros(3)
    Observations=np.asarray(y.at(coordinates))
    # for i in range(3):
    #     Observations[i]=y.at(coordinates[i])
    P0=M(coordinates,Observations,f) # this is the distance function in development.
    assert(1-any(P0.dat.data>1e-14))


@pytest.mark.xfail(reason="Expected to fail. Waiting for missing functionality. Function @M")
def test_distance_function_perturbed(): # this should return >0 distances from perturbed observations to function for arbitrary coordinate
    # Define function spaces and functions for the observation and function that distance is to be found
    n0=10
    N0=100
    Mesh=RectangleMesh(n0,n0,1,1,quadrilateral=False)
    ObsMesh=RectangleMesh(N0,N0,1,1,quadrilateral=False)
    V=FunctionSpace(Mesh,"DG",1)
    Y=FunctionSpace(ObsMesh,"DG",1)
    ex=Expression("sin(x[0]*2*amp)",amp=np.pi)
    y=Function(Y); y.interpolate(ex)
    f=Function(V); f.interpolate(ex)
    # Evaluate observations 
    coordinates=[]
    for i in range(3):
        coordinates.append(np.array([0.2*(i+1),0.2*(i+1)]))
    Observations=np.asarray(y.at(coordinates))+np.random.normal(0,0.01,1)
    #Observations=np.zeros(3)
    #for i in range(3):
    #    Observations[i]=ObservationOperator(coordinates[i])+np.random.normal(0,0.01,1)
    P0=M(coordinates,Observations,f) # this is the distance function in development.
    assert(any(P0.dat.data>1e-14))


if __name__ == '__main__':
    import os
    pytest.main(os.path.abspath(__file__))

