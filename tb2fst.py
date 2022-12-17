""" read one or more toolbox files, dicts or full text
	extrapolate mapping between markers, only full form match.
	The result is equivalent with Toolbox automated annotation,
	except ambiguities are just spelled out.
	In the FST formalization, however, that can be more flexibly combined
	with other FST technology, e.g., for spelling normalization.
	
	Note that you can feed in dictionary or annotation files, but that
	the recorded frequencies are meaningful only for annotation files.
	In particular, we do not evaluate for markers that provide external
	frequency information, say \fq in a dictionary.
	"""

import sys,os,re, argparse
import toolbox
from io import StringIO
from pprint import pprint


SFST_REPLACEMENTS={"=":"\\=", "-":"\\-", "|":"\\|"}

def escape(string:str, replacements:dict):
	""" apply all replacements that apply, in the order as they are stored in replacements, from left to right """
	for src,tgt in replacements.items():
		if src in string:
			string=tgt.join(string.split(src))
	return string

class FSTGenerator:

	""" Internally, the FST generator only creates a dict for mapping tokens from source marker layer to target marker layer.
		We also track frequencies. The result can then be serialized as an FST grammar. """

	source=None
	target=None
	record_keys=[]
	src2tgt2freq=None
	segment_separator=None

	def __init__(self, source, target, record_keys=["\\id","\\ref"], segment_separator=" "):
		""" source and target are markers for which the mapping is to be produced.
			record_keys are delimiters for individual examples, are used for grouping 
			records during parsing.
			segment_separator is inserted between segments of the target layer, e.g., between morphemes.
			For word-to-word replacements, this isn't used.

			Note: target must be after source in the glossing

			"""

		self.src2tgt2freq={}
		self.record_keys=record_keys
		self.segment_separator=segment_separator

		# convenience functions for entry via command line
		# note that we don't do that for record_keys because
		# these are normally not read from command line
		if not source.startswith("\\"):
			source="\\"+source
		if not target.startswith("\\"):
			target="\\"+target

		for marker in [source, target]:
			if not re.match(r"^\\[a-zA-Z0-9]+$",marker):
				sys.stderr.write(f"warning: marker {marker} doesn't seem to be well-formed, we expect markers to match the expression \\[a-zA-Z0-9]+\n")

		if source==target:
			raise Exception("source marker must not be identical to target marker")

		self.source=source
		self.target=target

	def add(self, input):
		""" input is either a file name, a string, a list of these or a stream """
		if isinstance(input,str):
			# string denotes a file
			if os.path.exists(input):
				with open(input,"rt",errors="ignore") as input:
					self.add(input)
					return
			# string may be a toolbox text => stream
			input=StringIO(input)

		if isinstance(input,list):
			# list => iterate
			for i in input:
				self.add(i)
			return

		# => processing an IGT stream
		alignments={self.target:self.source}

		# read, line-based
		raw=toolbox.read_toolbox_file(input)
		
		# aggregate according to document and record ids
		for (meta,record) in toolbox.records(raw,self.record_keys):
			meta=" ".join([ " ".join( [ f"{x}" for  x in i ]) for i in sorted(meta.items()) ])

			# merge multi-line glosses
			record=toolbox.normalize_record(record,[self.source,self.target])
			# tokenize and align spans between relevant marker layers
			mkr2span= { mkr: span \
						for mkr, span \
						in toolbox.align_fields(record, alignments=alignments) \
						if mkr in [self.source,self.target] }
			if len(mkr2span)==2:
				sys.stderr.write(f"\rprocess {meta}       ")
				sys.stderr.flush()
				for src,tgt in mkr2span[self.target]:
					tgt=self.segment_separator.join(tgt)
					if not src in self.src2tgt2freq: self.src2tgt2freq[src]={}
					if not tgt in self.src2tgt2freq[src]: self.src2tgt2freq[src][tgt]=0
					self.src2tgt2freq[src][tgt]+=1
		sys.stderr.write(f"\rprocessed {meta}       \n")

	def sfst(self, output=None,freq_cutoff=0,ignore_case=True):
		""" spellout as SFST grammar

			use freq_cutoff to eliminate low-frequency mappings 
			if output is a stream or a file (name), write there,
			otherwise, return a string 
		"""

		if output==None:
			output=StringIO()
			self.sfst(freq_cutoff=freq_cutoff,output=output)
			return output.getvalue()

		if isinstance(output,str):
			with open(output,"wt") as output:
				return self.sfst(freq_cutoff=freq_cutoff,output=output)

		# output stream
		name=re.sub(r"[^A-Z0-9_]","",(self.source+"_to_"+self.target).upper())
		name=f"${name}$"
		vals=[]
		salph=set()
		talph=set()
		for src in sorted(self.src2tgt2freq):
			for tgt,freq in sorted(self.src2tgt2freq[src].items()):
				if freq>freq_cutoff:
					salph.update(src)
					talph.update(tgt)

					# escape or filter here, if necessary
					src=escape(src,SFST_REPLACEMENTS)
					tgt=escape(tgt,SFST_REPLACEMENTS)
					vals.append("{"+src+"}:{"+tgt+"} % freq "+str(freq))
		if len(vals)==0:
			raise Exception(f"empty grammar with frequency cutoff {freq_cutoff}")
		
		sys.stderr.write(f"=> {len(vals)} replacement rules\n")
		vals=" \\\n\t| ".join(vals)

		alph="".join(sorted(set(list(salph)+list(talph))))
		salph="".join(sorted(salph))
		talph="".join(sorted(talph))
		
		if ignore_case:
			case_rule="["+"".join(sorted(set(alph.upper())))+"]:["+"".join(sorted(set(alph.lower())))+"]"
			case_rule+=" ["+"".join(sorted(set(alph.lower())))+"]:["+"".join(sorted(set(alph.upper())))+"]"

		output.write(f"""
#SALPH#={escape(salph,SFST_REPLACEMENTS)}
#TALPH#={escape(talph,SFST_REPLACEMENTS)}
ALPHABET=[#SALPH#] [#TALPH#] {case_rule}

{name}={vals}

.+ || [#SALPH#]+ || {name} || [#TALPH#]+\n""")

		output.flush()

if __name__ == "__main__":

	args=argparse.ArgumentParser(description="""
		Given two Toolbox markers and one or more Toolbox files, extrapolate an FST 
		for dictionary-based (lookup-based) annotation from source marker to target 
		marker. At the moment, we only support SFST output.
		Note that this has only been tested so far for full-word replacement, not for
		files with morphological segmentation. 
		""")

	args.add_argument("source",type=str,help="source marker, e.g. \\tx for textual input")
	args.add_argument("target",type=str,help="target marker, e.g. \\lm for lemmas")
	args.add_argument("files",type=str,nargs="*", help="Toolbox files from which a full-form mapping is to be extrapolated; if empty, read from stdin", default=[])
	args.add_argument("-f","--freq_cutoff",type=int,help="frequency cutoff to eliminate hapaxes, set to 0 or smaller to keep all", default=0)
	args.add_argument("-o","--output", type=str, help="output file to write the FST grammar into (by default, write to stdout)")
	args.add_argument("-i","--ignore_case", action="store_true", help="if set, tolerate upper and lower case variation in the input (in generation)")
	args=args.parse_args()

	if args.output==None:
		args.output=sys.stdout
	else:
		args.output=open(args.output,"wt")

	if len(args.files)==0:
		sys.stderr.write(f"reading Toolbox data from stdin, note that we require markers {args.source} and {args.target} in the data\n")
		args.files.append(sys.stdin)

	me=FSTGenerator(args.source, args.target)
	me.add(args.files)
	# pprint(me.src2tgt2freq)

	me.sfst(args.output,freq_cutoff=args.freq_cutoff, ignore_case=args.ignore_case)
	args.output.flush()
	args.output.close()