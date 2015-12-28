import pdb
import numpy as np
import simtk.unit as unit
import simtk.openmm as mm
from simtk.openmm import app
from copy import deepcopy
from customexamolforces import *

#=== DEFINE CONSTANTS  ===
DEBUG_MODE = False
#ff = app.ForceField('xmlfiles/gaff.xml', 'xmlfiles/examol.xml', 'xmlfiles/examolresidue.xml', 'tip3p.xml')
if DEBUG_MODE:
    ff = app.ForceField('xmlfiles/gaff.xml', 'xmlfiles/examolcharge.xml', 'xmlfiles/testresidue.xml', 'tip3p.xml')
else:
    ff = app.ForceField('xmlfiles/gaff.xml', 'xmlfiles/examolcharge.xml', 'xmlfiles/examolresiduecharge.xml', 'tip3p.xml')
#Nonbonded methods
NBM=app.PME
#NBM=app.NoCutoff
#Nonbonded cutoff
NBCO=9*unit.angstrom
#Constraint
constraints=app.HBonds
# rigid water
rigidWater=True
#Ewald Tolerance 
eET=0.0005
#=== END CONSTANTS ===

def listCoordsToNumpy(Coords):
    #Cast the coordinates in a list format to numpy format. Some getPositions() functions allow asNumpy=True keyword, others (like the modeler) do not. This function handles thoes that do not
    nCoords = len(Coords)
    numpyCoords = np.zeros([nCoords,3])
    baseunit = Coords.unit
    for n in xrange(nCoords):
        numpyCoords[n,:] = Coords[n].value_in_unit(baseunit)
    return numpyCoords * baseunit

def stripAndUnifyUnits(A, B):
    #Cast both A and B to the same base unit and return them stripped along with the base
    #Many NumPy functions loose do not preserve units, this function is mostly used for this
    baseunit = A.unit
    return A.value_in_unit(baseunit), B.value_in_unit(baseunit), baseunit

def loadamber(basefilename, NBM=NBM, NBCO=NBCO, constraints=constraints, rigidWater=rigidWater, eET=eET):
    prmtop = app.AmberPrmtopFile(basefilename + '.prmtop')
    inpcrd = app.AmberInpcrdFile(basefilename + '.inpcrd')
    system = prmtop.createSystem(
     nonbondedMethod=NBM,
     nonbondedCutoff=NBCO,
     constraints=constraints,
     rigidWater=rigidWater,
     ewaldErrorTolerance=eET)
    return system

def loadpdb(basefilename, NBM=NBM, NBCO=NBCO, constraints=constraints, rigidWater=rigidWater, eET=eET, boxbuffer=0.2):
    #Box Buffer is % extra away from peak-to-peak distances to draw pbc
    pdbfile = app.PDBFile(basefilename + '.pdb')
    #Check for not PBC
    if pdbfile.topology.getPeriodicBoxVectors() is None:
        pos = pdbfile.getPositions(asNumpy=True)
        #Peak to peak distances across all atoms
        ptpdistances = np.ptp(pos,axis=0)
        #Maximum absolute coordinate
        absmaxdists = np.abs(pos).max(axis=0)
        #3x3 box vector, sum of abs + ptp, then scaled up by box buffer, and reapply unit
        boxvecs = np.eye(3)*(absmaxdists + ptpdistances) * (1+boxbuffer) * pos.unit
        pdbfile.topology.setPeriodicBoxVectors(boxvecs)
    system = ff.createSystem(
     pdbfile.topology,
     nonbondedMethod=NBM,
     nonbondedCutoff=NBCO,
     constraints=constraints,
     rigidWater=rigidWater,
     ewaldErrorTolerance=eET)
    #FF sanity check. Make sure there are an equal number of bonds/constraints in system as there are in topology
    #Assuming not multiple constraints per atom
    if len(pdbfile.topology._bonds) != system.getForce(0).getNumBonds() + system.getNumConstraints():
        print("WARNING: {0:s} does not have matching topology and system bonds/constraints!".format(basefilename))
    return system, pdbfile

def writePDBCoords(filename, topology, positions):
    #Cast positions into on-demand generator
    def posgen(positions):
        nPos = positions.shape[0]
        i = 0
        while i < nPos:
            yield positions[i,:]
            i += 1

    Pgen = posgen(positions)
    #Write out a PDB file positions based on the topology names and positions
    wrtiestr = ''
    writestr += "REMARK CREATED WITH EXAMOL\n"
    #PBC
    writestr += "CRYSTL   {0:0.3f}   {1:0.3f}   {2:0.3f}  90.00  90.00  90.00 P 1           1\n".format()
    writestr += "MODEL\n"
    #                   num           name         res        chainid    resid
    pointstr = "ATOM {atnum: >6d} {atname: >4s} {resname:>3s} {chain:1s}{resid: >4d}      {xcoord: >5.3f}  {ycoord: >5.3f}  {zcoord: >5.3f}  1.00  0.00 {element: >11s}\n"
    #                idnum
    termstr = "TER {atnum: >6d}      {resname:>3s} {chain:1s}{resid: >4d}\n"
    #Construct atoms
    getPos 
    ci = 0 
    cstr = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ai = 1
    for chain in topology.chains():
        cs = cstr[ci]
        ri = 1
        for res in chain.resudies():
            resname = res.name
            for atom in res.atoms():
                x,y,z = next(posgen).value_in_unit(unit.angstrom)
                name = atom.name
                element = atom.element
                atdic = {"atnum":ai, "atname":name, "resname":resname, "chain":cs, "resid":ri, "xcoord":x, "ycoord":y, "zcoord":z, "element":element }
                writestr += pointstr.format(atdic)
            ri += 1
        #Remove one so last residue is used as term
        ri -= 1
        terdic = {"atnum":ai, "resname":resname, "chain":cs, "resid":ri}
        writestr += termstr.format(terdic)
        ci +=1
    return


def addRParticles(mainSystem, coreSystem, corecoords, Rsystem, Rcoords):
    #Detect differences between core and R group
    Ncore = coreSystem.getNumParticles()
    NR = Rsystem.getNumParticles()
    Nmain = mainSystem.getNumParticles()
    new_atoms = xrange(Ncore,NR)
    #Attach R group to main system
    for new_atom in new_atoms:
        mainSystem.addParticle(Rsystem.getParticleMass(new_atom))
        #Map this particle to the new atom number
    ##Atoms, bonds, angles, torsions, dihedrals
    return range(Nmain, mainSystem.getNumParticles())

def maxPBC(targetSystem, additionalSystem, percentNudge=1):
    #set the periodic boundary vectors (PBV) of the target system to the max of target and additional
    addPBV = additionalSystem.getDefaultPeriodicBoxVectors()
    targetPBV = targetSystem.getDefaultPeriodicBoxVectors()
    newPBV = [[1,0,0] * addPBV[0].unit, [0,1,0] * addPBV[1].unit, [0,0,1] * addPBV[2].unit]
    for idim in range(3):
        vecmax = np.max((addPBV[idim][idim],targetPBV[idim][idim]))
        newPBV[idim] *= vecmax.value_in_unit(newPBV[idim].unit)*percentNudge
    targetSystem.setDefaultPeriodicBoxVectors(*newPBV)
    return

def appendPositions(mainSet, additionalSet):
    #Append additionalSet positions to the mainSet positions and return mainSet
    mainSet, additionalSet, baseunit = stripAndUnifyUnits(mainSet, additionalSet)
    mainSet = np.append(mainSet,additionalSet,axis=0)
    return mainSet * baseunit

def alignCoords(referenceCoords, toXformCoords, weights=None, pointOfOrigin=0):
    #Code from "Python Programming for Biology: Bioinformatics and Beyond" pg 301-302
    #Accepts a PDBFile.getPositions(asNumpy=True) argument for referenceCoords and toXformCoords
    #Point of Origin is the atom to translate to first
    refCoords, xformCoords, baseunit = stripAndUnifyUnits(referenceCoords, toXformCoords)
    nalign = len(refCoords)
    nxform = len(xformCoords)
    #Find COGeometry of the known common structureand translate
    refCenter = np.mean(refCoords, axis=0)
    xformCenter = np.mean(xformCoords[:nalign], axis=0)
    refCoords -= refCenter
    xformCoords -= xformCenter
    #Compute rotation
    if weights is None:
        weights = np.zeros(nxform)
        weights[:nalign] = 1 
        weights = np.ones(nalign)
    rMat = np.dot(xformCoords[:nalign,:].T*weights, refCoords)
    rMat1, scales, rMat2 = np.linalg.svd(rMat)
    sign = np.linalg.det(rMat1) * np.linalg.det(rMat2)
    if sign < 0:
        rMat1[:,2] *= -1
    rotation = np.dot(rMat1, rMat2)
    #Rotate new coordinates
    newCoords = np.dot(xformCoords, rotation)
    #Remove COG translation
    newCoords += refCenter
    return newCoords * baseunit

def addToMainTopology(mainTopology, addontopology, Ncore, addBonds=False):
    #Add the atoms from the addontopology to the mainTopology
    #Atom->Residue->Chain->Topology
    #Chain ownership has to be passed from the addontopology to the main topology before adding the atom to the main topology
    #Alternatley, choose the residue that the atom is attached to as the 
    #Grab the main residue
    atommap = []
    for residue in mainTopology.residues():
        mainres = residue
        break
    coreAtoms = [atom for atom in mainTopology.atoms()][:Ncore]
    for atom in addontopology.atoms():
        if int(atom.id) > Ncore:
            atomMain = mainTopology.addAtom(atom.name, atom.element, mainres)
            atommap.append((atom,atomMain))
        else: #Map the core atoms
            #Atom id's start with numbers, -1 to align with list index
            atommap.append((atom, coreAtoms[int(atom.id)-1]))
    natoms = len(atommap)
    if addBonds:
        for bond in addontopology.bonds():
            bondAddA1, bondAddA2 = bond #Break up atom bonds
            bondMainA1 = None
            bondMainA2 = None
            for i in xrange(natoms):
                if bondAddA1 is atommap[i][0]:
                    bondMainA1 = atommap[i][1]
                if bondAddA2 is atommap[i][0]:
                    bondMainA2 = atommap[i][1]
                if bondMainA1 is not None and bondMainA2 is not None:
                    #Stop loop if both atoms found
                    break
            #Only add if not in core atoms
            if bondMainA1 not in coreAtoms or bondMainA2 not in coreAtoms:
                mainTopology.addBond(bondMainA1, bondMainA2)
    return

def copyTopologyBtoA(topA, topB):
    #Function to add on topology B to topology A by a copy.
    #This is a FULL copy
    #Map linking atoms in B to A so I can make bonds
    atommap = []
    for chainB in topB.chains():
        chainA = topA.addChain()
        for resB in chainB.residues():
            resA = topA.addResidue(resB.name, chainA)
            for atomB in resB.atoms():
                atomA = topA.addAtom(atomB.name, atomB.element, resA)
                atommap.append((atomB,atomA))
    natoms = len(atommap)
    for bond in topB.bonds():
        bondBA1, bondBA2 = bond #Break up atom bonds
        bondAA1 = None
        bondAA2 = None
        for i in xrange(natoms):
            if bondBA1 is atommap[i][0]:
                bondAA1 = atommap[i][1]
            if bondBA2 is atommap[i][0]:
                bondAA2 = atommap[i][1]
            if bondAA1 is not None and bondAA2 is not None:
                #Stop loop if both atoms found
                break
        topA.addBond(bondAA1, bondAA2)
    return

#Load the core
#coreSystem = loadamber('testcore')
coreSystem, corecoords = loadpdb('pdbfiles/core/corec')
corePositions = corecoords.getPositions(asNumpy=True) #Positions of core atoms (used for alignment)
Ncore = coreSystem.getNumParticles()


#Start mainSystem
mainSystem = deepcopy(coreSystem)
'''
Note: The mainSystem is NOT built from the combined topologies because that would add torsions and angle forces to R-groups on the same core carbon, which we wond want.
'''
mainTopology = deepcopy(corecoords.getTopology())
mainPositions = deepcopy(corePositions)
mainBondForce = getArbitraryForce(mainSystem, mm.HarmonicBondForce)
mainAngleForce = getArbitraryForce(mainSystem, mm.HarmonicAngleForce)
mainTorsionForce = getArbitraryForce(mainSystem, mm.PeriodicTorsionForce)
mainNonbondedForce = getArbitraryForce(mainSystem, mm.NonbondedForce)
mainCMRForce = getArbitraryForce(mainSystem, mm.CMMotionRemover)

#Start the Rgroups
if DEBUG_MODE:
    #DEBUG: 3 sites, 1 R-group per site (hydrogens)
    Ni = 3 #Number of ith groups
    Nj = 1 #Number of jth groups
else:
    Ni = 3 #Number of ith groups
    Nj = 10 #Number of jth groups
#allocate the housing objects
Rsystems=np.empty([Ni,Nj],dtype=np.object)
Rcoords=np.empty([Ni,Nj],dtype=np.object)
RMainAtomNumbers = np.empty([Ni,Nj],dtype=np.object)
#Import the Rgroups
for i in xrange(Ni):
    for j in xrange(Nj):
        #Rgroup = loadamber('testR')
        #Rsystems[i,j], Rcoords[i,j] = loadpdb('j1mt')
        Rsystem, Rcoord = loadpdb('pdbfiles/i%d/j%dc'%(i+1,j+1))
        Rsystems[i,j], Rcoords[i,j] = Rsystem, Rcoord
        #Add the Rgroup atoms to the main system
        RMainAtomNumber = addRParticles(mainSystem, coreSystem, corecoords, Rsystem, Rcoord)
        RMainAtomNumbers[i,j] = RMainAtomNumber
        RPos = Rcoord.getPositions(asNumpy=True)
        #align the new group to the core structure (to which the main was already alligned)
        alignedPositions = alignCoords(corePositions, RPos)
        #Append the newly aligned R-group structure to the main structure
        mainPositions = appendPositions(mainPositions,alignedPositions[Ncore:,:])
        #set PBC's, probably not needed here
        maxPBC(mainSystem, Rsystem)
        #Add topologies together, only needed to add solvent to the system
        addToMainTopology(mainTopology, Rcoord.getTopology(), Ncore)
        mainTopology.setPeriodicBoxVectors(mainSystem.getDefaultPeriodicBoxVectors())
        # === Add forces (exclusions later, for now, just get in all the defaults) ===
        for constraintIndex in range(Rsystem.getNumConstraints()):
            atomi, atomj, r0 = Rsystem.getConstraintParameters(constraintIndex)
            atomi, atomj = mapAtomsToMain([atomi, atomj], RMainAtomNumber, Ncore)
            if atomi >= Ncore or atomj >= Ncore:
                mainSystem.addConstraint(atomi, atomj, r0)
        for forceIndex in xrange(Rsystem.getNumForces()):
            referenceForce = Rsystem.getForce(forceIndex)
            if isinstance(referenceForce, mm.HarmonicBondForce):
                nRBonds = referenceForce.getNumBonds()
                for bondIndex in xrange(nRBonds):
                    atomi, atomj, eqdist, k = referenceForce.getBondParameters(bondIndex)
                    #if atomi >= Ncore or atomj >= Ncore: pdb.set_trace()
                    #Map atoms to core system
                    atomi, atomj = mapAtomsToMain([atomi, atomj], RMainAtomNumber, Ncore)
                    if atomi >= Ncore or atomj >= Ncore:
                        mainBondForce.addBond(atomi, atomj, eqdist, k)
            elif isinstance(referenceForce, mm.HarmonicAngleForce):
                customAngleForce = addAngleForceWithCustom(mainAngleForce, referenceForce, RMainAtomNumber, i, j, Ncore)
                customAngleForce.setForceGroup(i+1)
                mainSystem.addForce(customAngleForce)
            elif isinstance(referenceForce, mm.PeriodicTorsionForce):
                customTorsionForce = addTorsionForceWithCustom(mainTorsionForce, referenceForce, RMainAtomNumber, i, j, Ncore)
                customTorsionForce.setForceGroup(i+1)
                mainSystem.addForce(customTorsionForce)
            elif isinstance(referenceForce, mm.NonbondedForce):
                #Add the particle to the main nonbonded force. Custom will come after
                nParticles = referenceForce.getNumParticles()
                for atomi in xrange(nParticles):
                    q, sig, epsi = referenceForce.getParticleParameters(atomi)
                    (atomi,) = mapAtomsToMain([atomi], RMainAtomNumber, Ncore) #If you dont trap the returned atomi, it returns a list of atomi, e.g. [0], which is > int for some reason?
                    if atomi >= Ncore:
                        mainNonbondedForce.addParticle(q, sig, epsi)
                nException = referenceForce.getNumExceptions()
                for exceptionIndex in xrange(nException):
                    atomi, atomj, chargeProd, sig, epsi = referenceForce.getExceptionParameters(exceptionIndex)
                    atomi, atomj = mapAtomsToMain([atomi, atomj], RMainAtomNumber, Ncore)
                    if atomi >= Ncore or atomj >= Ncore:
                        mainNonbondedForce.addException(atomi, atomj, chargeProd, sig, epsi)
                    
######## BRING IN SOLVENT ##########
#Adjust the residue in the main topology to match the combined name so the modeler does not throw an error
for res in mainTopology.residues():
    res.name = 'COC'
#Add water with the modeler
modeller = app.Modeller(mainTopology, mainPositions)
modeller.addSolvent(ff, padding=1.2*unit.nanometer)
#Deelete non solvent residues. This includes the neutralizing ions which will be added since we have not handled electrostatics yet
modeller.delete([res for res in modeller.topology.residues() if res.name == 'COC' or res.name == 'CL' or res.name=='NA'])
copyTopologyBtoA(mainTopology, modeller.topology)
#Get Positions
modellerCoords = listCoordsToNumpy(modeller.getPositions())
#Combine positions
mainPositions = appendPositions(mainPositions, modellerCoords)
#Combine solvent with system, this can probably can be made into function form at some point
addSystem = ff.createSystem( 
 modeller.topology,
 nonbondedMethod=NBM,
 nonbondedCutoff=NBCO,
 constraints=constraints,
 rigidWater=rigidWater,
 ewaldErrorTolerance=eET)
Noriginal = mainSystem.getNumParticles()
Nnew = addSystem.getNumParticles()
maxPBC(mainSystem, addSystem, percentNudge=1.0)
mainTopology.setPeriodicBoxVectors(mainSystem.getDefaultPeriodicBoxVectors())
solventNumbers = range(Noriginal,Nnew+Noriginal)
for atomIndex in xrange(Nnew):
    mainSystem.addParticle(addSystem.getParticleMass(atomIndex))
for constraintIndex in range(addSystem.getNumConstraints()):
    atomi, atomj, r0 = addSystem.getConstraintParameters(constraintIndex)
    mainSystem.addConstraint(solventNumbers[atomi], solventNumbers[atomj], r0)
for forceIndex in xrange(addSystem.getNumForces()):
    referenceForce = addSystem.getForce(forceIndex)
    if isinstance(referenceForce, mm.HarmonicBondForce):
        nRBonds = referenceForce.getNumBonds()
        for bondIndex in xrange(nRBonds):
            atomi, atomj, eqdist, k = referenceForce.getBondParameters(bondIndex)
            mainBondForce.addBond(solventNumbers[atomi], solventNumbers[atomj], eqdist, k)
    elif isinstance(referenceForce, mm.HarmonicAngleForce):
        nAngle = referenceForce.getNumAngles()
        for angleIndex in xrange(nAngle):
            atomi, atomj, atomk, angle, k = referenceForce.getAngleParameters(angleIndex)
            mainAngleForce.addAngle(solventNumbers[atomi], solventNumbers[atomj], solventNumbers[atomk], angle, k)
    elif isinstance(referenceForce, mm.PeriodicTorsionForce):
        nTorsion = referenceForce.getNumTorsions()
        for torsionIndex in xrange(nTorsion):
            atomi, atomj, atomk, atoml, period, phase, k = referenceForce.getTorsionParameters(torsionIndex)
            mainTorsionForce.addTorsion(solventNumbers[atomi], solventNumbers[atomj], solventNumbers[atomk], solventNumbers[atoml], period, phase, k)
    elif isinstance(referenceForce, mm.NonbondedForce):
        #Add the particle to the main nonbonded force. Custom will come after
        nParticles = referenceForce.getNumParticles()
        for atomi in xrange(nParticles):
            q, sig, epsi = referenceForce.getParticleParameters(atomi)
            mainNonbondedForce.addParticle(q, sig, epsi)
        nException = referenceForce.getNumExceptions()
        for exceptionIndex in xrange(nException):
            atomi, atomj, chargeProd, sig, epsi = referenceForce.getExceptionParameters(exceptionIndex)
            mainNonbondedForce.addException(solventNumbers[atomi], solventNumbers[atomj], chargeProd, sig, epsi)


#=== NONBONDED AND CUSTOM NONBONDED ===
#Now that all atoms are at least in the system, build the (custom) nonbonded forces
buildNonbonded(mainSystem, coreSystem, Rsystems, RMainAtomNumbers, solventNumbers, Ni, Nj)

#=== ATTACH INTEGRATOR, TEMPERATURE/PRESSURE COUPLING, AND MAKE CONTEXT ===
equilibriumTemperature = 298*unit.kelvin
integrator = mm.LangevinIntegrator(equilibriumTemperature, 1.0/unit.picosecond, 2*unit.femtosecond)
barostat = mm.MonteCarloBarostat(1*unit.bar, 298*unit.kelvin, 1)
#mainSystem.addForce(barostat)
platform = mm.Platform.getPlatformByName('OpenCL')

#for ndx in xrange(mainSystem.getNumForces()):
#    print ndx, mainSystem.getForce(ndx)

#Set the positions so all particles are in the box and do no wrap oddly
box=mainSystem.getDefaultPeriodicBoxVectors()
box = np.array([unit.norm(vector.value_in_unit(unit.nanometer)) for vector in box])*unit.nanometer
mincoords = np.min(mainPositions,axis=0)
newPositions = mainPositions - mincoords
nudgeDistance = (box - newPositions.max(axis=0))/2
newPositions += nudgeDistance
mainPositions = newPositions

#Quick code to create the PDB file with all the correct CONNECT entries (visualization)
#Atommaps from PDB file
#amap = range(1,Noriginal+1) #Base 1
#amap.extend(range(Noriginal+1+1, Nnew+Noriginal+1+1)) #Base 1, ter command occupies 1
#nC = mainSystem.getNumConstraints()
#nB = 0
#bondforces = []
#for forceidx in xrange(mainSystem.getNumForces()):
#    force = mainSystem.getForce(forceidx)
#    if isinstance(force, mm.HarmonicBondForce) or isinstance(force, mm.CustomBondForce):
#        bondforces.append(force)
#        nB += force.getNumBonds()
#bondlist = np.zeros([nB+nC, 2], dtype=int)
#count = 0
#for constraint in xrange(nC):
#    atomi, atomj, r0 = mainSystem.getConstraintParameters(constraint)
#    bondlist[count,:] = (amap[atomi], amap[atomj])
#    count +=1
#for force in bondforces:
#    for bond in xrange(force.getNumBonds()):
#        bondparam = force.getBondParameters(bond)
#        atomi, atomj = bondparam[0], bondparam[1]
#        bondlist[count,:] = (amap[atomi], amap[atomj])
#        count +=1
#conline = "CONECT{a1: >5d}{a2: >5d}\n"
#output = ''
#for bond in xrange(nB+nC):
#    output += conline.format(a1=bondlist[bond,0], a2=bondlist[bond,1])
#file = open('connects.pdb', 'w')
#file.write(output)
#file.close()
#pdb.set_trace()


#DEBUG: Testing built in reporters to see if I need something else
#simulation = app.Simulation(mainTopology, mainSystem, integrator, platform)
#simulation.context.setPositions(mainPositions)
#simulation.context.setVelocitiesToTemperature(equilibriumTemperature)
#reporter = app.PDBReporter('trajectory.pdb',1)
##reporter = app.DCDReporter('trajectory.dcd',1)
#reporter.report(simulation, simulation.context.getState(getPositions=True,getParameters=True, enforcePeriodicBox=True))
#pdb.set_trace()
#simulation.minimizeEnergy(1.0 * unit.kilojoules_per_mole / unit.nanometers, 0)
#reporter.report(simulation, simulation.context.getState(getPositions=True,getParameters=True, enforcePeriodicBox=True))
##reporter.report(simulation, simulation.context.getState(getPositions=True,getParameters=True))
#simulation.reporters.append(reporter)
#print simulation.context.getState(getEnergy=True).getPotentialEnergy()
#pdb.set_trace()
#simulation.step(1)

#Test taking a formal step to see if wrapping is handled correctly and if energies go to NaN
context = mm.Context(mainSystem, integrator, platform)

#=== MINIMIZE ENERGIES ===
context.setPositions(mainPositions)
context.setVelocitiesToTemperature(equilibriumTemperature)
#pdb.set_trace()
context.applyConstraints(1E-6)
#Assign random lambda vector (testing)
randLam = np.random.random(Ni*Nj)
#randLam = np.zeros(Ni*Nj)
#randLam[8:-1:10] = 1
randLam = np.ones(Ni*Nj) * 0.9
assignLambda(context, randLam, Ni, Nj, skipij2=False)
checkLam = getLambda(context, Ni, Nj)
platformMode = platform.getPropertyValue(context, 'OpenCLPrecision')
platform.setPropertyValue(context, 'OpenCLPrecision', 'double')
pdb.set_trace()
computeBasisEnergy(context, Ni, Nj)
mm.Platform.setPropertyValue(context, 'OpenCLPrecision', platformMode)
print context.getState(getEnergy=True, groups=1).getPotentialEnergy()
print context.getState(getEnergy=True).getPotentialEnergy()
#Minimize positions
mm.LocalEnergyMinimizer.minimize(context, 1.0 * unit.kilojoules_per_mole / unit.nanometers, 0)

#Test energy Evaluation
computeBasisEnergy(context, Ni, Nj)
pdb.set_trace()
    
#Test a step
integrator.step(10)

#Sanity Checks
state = context.getState(getPositions=True,enforcePeriodicBox=True,getEnergy=True)
#Check energies
energy = state.getPotentialEnergy()
print energy
#Check Positions
coords = state.getPositions(asNumpy=True)
print coords

pdb.set_trace()
