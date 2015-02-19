# Keyframe Reducer v1.15 by Richard Frazer 
# http://www.richardfrazer.com/tools-tutorials/keyframe-reduction-script-for-nuke/

import nuke
import math
import nukescripts

class doReduceKeyframesPanel(nukescripts.PythonPanel):
	def __init__(self, node):
	
		#get reference of tKey knob
		knob_names = nuke.animations()	
		knob_name_with_suffix = knob_names[0]
		print"knob_name_with_suffix "
		print knob_name_with_suffix
		knob_name = getKnobName(knob_name_with_suffix)
		k = nuke.thisNode()[knob_name]

		#so that our default frame range can be the length of it's keyframes
		tFirst = first_keyframe_location(k)
		tLast = last_keyframe_location(k)
		
		nukescripts.PythonPanel.__init__(self, 'Reduce keyframes in selected animation?')
		
		# CREATE KNOBS
		self.tFrameRange = nuke.String_Knob('tFrameRange', 'Frame Range', '%s-%s' % (tFirst, tLast))
		self.tErrorThreshold = nuke.Int_Knob('tErrorThreshold', 'Error threshold')
		self.tErrorThreshold.setValue(2)
		
		self.pcText = nuke.Text_Knob( '%' )
		self.pcText.clearFlag( nuke.STARTLINE )
		
		# ADD KNOBS
		for k in (self.tFrameRange, self.tErrorThreshold, self.pcText):
			self.addKnob(k)


def getKnobName(knob_name_with_suffix):
	
	# THIS NEEDS IMPROVING
	# if we try to run this script on transforms applied to Beziers or Layers within a RotoPaint node, they fall under the knob "curves"
	# i.e. "curves.Bezier1.rotate" or "curves.translate.x". Nuke gets a bit weird when trying to expression link to these attributes, the 
	# naming conventions start getting randomly inconsistent. It probably all falls under the _curvelib.AnimCTransform object type. 

	knob_name = knob_name_with_suffix.split(".")[0]
	print "knob_name " + knob_name
	return knob_name



def first_keyframe_location(k):

	#Returns the first frame which contains an animated keyframe for the selected node

	first_frames = []
	# Walk all the knobs of the object and check if they are animated.
	if k.isAnimated():
		for tOriginalCurve in k.animations():
			first_frames.append(tOriginalCurve.keys()[0].x)
		#print first_frames
		return int(min(first_frames))
	else:
		return nuke.root().firstFrame()
	
	
def last_keyframe_location(k):

	#Returns the last frame which contains an animated keyframe for the selected node

	last_frames = []
	# Walk all the knobs of the object and check if they are animated.
	if k.isAnimated():
		for tOriginalCurve in k.animations():
			tKeys = tOriginalCurve.keys()
			last_frames.append(tKeys[len(tKeys)-1].x)
		#print last_frames
		return int(min(last_frames))
	else:
		return nuke.root().lastFrame()
	
def getAngle(deltaH=None, deltaV=None):

	if(deltaH):
		angle = math.atan2(deltaV, deltaH)		
		if (deltaH < 0):
			angle = angle + math.pi			
	elif (deltaV > 0):		
		angle = math.pi / 2		
	elif (deltaV < 0):	
		angle = (3 * math.pi) / 2	
	else :
		angle = 0

	#Convert from radians to degrees 
	rAngle = math.degrees(angle)

	return rAngle 


def doReduceKeyframes():	

	p = doReduceKeyframesPanel(nuke.selectedNode())
		
	if p.showModalDialog(): #user did not hit cancel button

		undo = nuke.Undo()
		undo.begin("Reduce keyframes")  
				
		tErrorThreshold = p.tErrorThreshold.value()
		
		if (tErrorThreshold > 100):
			tErrorThreshold = 100
		
		if (tErrorThreshold < 1):
			tErrorThreshold = 1

		tFrameRange =  nuke.FrameRange( p.tFrameRange.value() )
		tFirstFrame = tFrameRange.first()
		tLastFrame = tFrameRange.last()
		
		knob_names = nuke.animations() # Returns the animations names under this knob

		j=0 #index for knob
		 
		for knob_name_with_suffix in knob_names: 
		
			
			knob_name = getKnobName(knob_name_with_suffix)
			
			# so that we can get at the knob object and do...
			k = nuke.thisNode()[knob_name]

			if(k.isAnimated(j)):
			
				tOriginalCurve = k.animation(j)
				
				tKeys = tOriginalCurve.keys()

				tOrigFirstFrame = tKeys[0].x
				
				tOrigLastFrame = tKeys[len(tKeys)-1].x
												
				tOrigKeys = len(tOriginalCurve.keys())


				if (tOrigKeys >2): #no point in reducing a straight line!

					x = nuke.selectedNode()					
					
					#create a temp knob to copy new keyframes into
					
					tempname = "temp_" + knob_name + str(j)
					
					tTempKnob = nuke.Double_Knob(tempname)
					
					tTempKnob.setAnimated()
					
					tTempKnob.setValueAt( tOriginalCurve.evaluate(tFirstFrame) , tFirstFrame )
					
					tTempKnob.setValueAt( tOriginalCurve.evaluate(tLastFrame) , tLastFrame )
			
					tTempCurve = tTempKnob.animation(0)

					#if we are only reducing keyframes on a smaller frame range, then copy the original keyframes into the other frames
										
					if(tFirstFrame > tOrigFirstFrame)|(tLastFrame < tOrigLastFrame):

						tKeys = x[knob_name].animation(j).keys()
						
						tCopyKeys = []

						for tKey in tKeys:																				
							if ((tKey.x < tFirstFrame) | (tKey.x > tLastFrame)):
								tCopyKeys.append(tKey)
						tTempKnob.animation(0).addKey(tCopyKeys)
					
					#do a quick check to see if 2 keyframes are enough
					deltaH = (tLastFrame - tFirstFrame)
					deltaV = ( tTempKnob.getValueAt(tLastFrame) - tTempKnob.getValueAt(tFirstFrame) )	 	
					tMasterSlope = 90 - getAngle (deltaH, deltaV) 
					if (tMasterSlope<0): tMasterSlope = tMasterSlope + 360;

					if ( meanAverageError(tOriginalCurve, tTempCurve, tFirstFrame, tLastFrame, tMasterSlope) < tErrorThreshold ):					
						print "looks like this selection of frames was a straight line"						
					else:
						#otherwise we run the keyframe reducing function on the selected frame range					
						recursion = findGreatestErrorFrame(tOriginalCurve, tFirstFrame, tLastFrame, tErrorThreshold, tTempKnob, tTempCurve, 0)	
					
					#copy our reduced keyframes from the temp knob back into our original knob
					x[knob_name].copyAnimation(j, tTempKnob.animation(0))
										
					#calculate how much we have reduced number of keyframes
					tFinalKeys = len(x[knob_name].animation(j).keys())
					tReductionPC = int( ( float(tFinalKeys) / float(tOrigKeys) ) * 100 )
										
					print knob_name + "[" + str(j) + "] had " + str(tOrigKeys) + " keys reduced to " + str(tFinalKeys) + " keys (" + str(tReductionPC) + "%)"


			else:
			
				print "No animation found in " + knob_name + " index " + str(j)
				
			j=j+1

		undo.end()
	
	

	
def findGreatestErrorFrame(tOriginalCurve=None, tFirstFrame=None, tLastFrame=None, tErrorThreshold=None, tTempKnob=None, tTempCurve=None, recursion=None):
	
	#print ("about to sub divide between frames " + str(frameStart) + " and " +str(frameEnd) )
	
	tErrorVal = 0
	tErrorFrame = tFirstFrame
	
	#find the base slope angle for the frame selection   
	deltaH = (tLastFrame - tFirstFrame)
	deltaV = ( tTempKnob.getValueAt(tLastFrame) - tTempKnob.getValueAt(tFirstFrame) )	 
	
	tMasterSlope = 90 - getAngle (deltaH, deltaV) 
	if (tMasterSlope<0): tMasterSlope = tMasterSlope + 360;
	
	print "tMasterSlope " + str(tMasterSlope)
	
	#check each frame in section and find which is furthest from the base slope	
	for f in range(tFirstFrame,tLastFrame+1):
	
		#trigonometry time! find length of 'hypotenuse' side		
		tHypotenuse = (tOriginalCurve.evaluate(f) - tTempCurve.evaluate(f))
		
		#use our 'sin' function to then calculate length of 'opposite' side - this is our distance between original and new keyframes	
		tOpposite = (math.sin(math.radians(tMasterSlope))*tHypotenuse)

		#our frame with the greatest error value is stored so we can add a keyframe to it later
		if (abs(tOpposite) > tErrorVal):
			tErrorVal = abs(tOpposite)
			tErrorFrame= f

	#find the value in the original curves at the greatest error frame 
	v = tOriginalCurve.evaluate(tErrorFrame)

	#copy this value into our new curves
	tTempKnob.setValueAt(v, tErrorFrame);

	
	#our section of frames has now been divided into 2.
	#we need to check both sections and see if they are within our error threshold
	firstErrorThreshold = meanAverageError(tOriginalCurve, tTempCurve, tFirstFrame, tErrorFrame, tMasterSlope)
	secondErrorThreshold = meanAverageError(tOriginalCurve, tTempCurve, tErrorFrame, tLastFrame, tMasterSlope)
	
	recursion = recursion+1
	
	#print "recursion " + str(recursion)

	#if they are not within threshold then we recursively call this function to divide them again
	if (firstErrorThreshold > tErrorThreshold):
		recursion = findGreatestErrorFrame(tOriginalCurve, tFirstFrame, tErrorFrame, tErrorThreshold, tTempKnob, tTempCurve, recursion)
	if (secondErrorThreshold > tErrorThreshold):
		recursion = findGreatestErrorFrame(tOriginalCurve, tErrorFrame, tLastFrame, tErrorThreshold, tTempKnob, tTempCurve, recursion)

	return recursion
	
	

def meanAverageError(tOriginalCurve=None, tNewCurve=None, tFirstFrame=None, tLastFrame=None, tMasterSlope=None):
	
	#function returns an error value, as a percent of the total height of the animation curve. 
	
	tHighVal = 0
	tLowVal = 0
	tValRange = 0
	tErrorTotal = 0
	tTotalFrames = 0
	tErrorPercent = 0

	for f in range(tFirstFrame,tLastFrame+1):
		v = tOriginalCurve.evaluate(f)
		if (v<tLowVal):
			tLowVal = v
		if (v>tHighVal):
			tHighVal = v
			
		#trigonometry time! find length of 'hypotenuse' side		
		tHypotenuse = (tOriginalCurve.evaluate(f) - tNewCurve.evaluate(f))
		
		#use our 'sin' function to then calculate length of 'opposite' side - this is our error value	
		tDifference = (math.sin(math.radians(tMasterSlope))*tHypotenuse)

		#tDifference = v - tNewCurve.evaluate(f)
		tErrorTotal = tErrorTotal + abs(tDifference)
		tTotalFrames +=1
		
	if tErrorTotal:
		tAverageError = tErrorTotal / tTotalFrames
		tValRange = tHighVal - tLowVal
		tErrorPercent =  100 * (tAverageError / tValRange)

	return tErrorPercent


	
