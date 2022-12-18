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
import warnings

SFST_REPLACEMENTS={
	"\\":"\\\\",
	"=":"\\=",
	 "-":"\\-",
	 "|":"\\|",
	 ",":"\\,",
	 ".":"\\.",
	"(":"\\(",
	")":"\\)",
	":":"\\:",
	"?":"\\?",
	"&":"\\&",
	" ":"\\ ",
	"*":"\\*",
	"[":"\\[",
	"]":"\\]",
	"!":"\\!"}

def escape(string:str, replacements:dict):
	""" apply all replacements that apply, in the order as they are stored in replacements, from left to right """
	for src,tgt in replacements.items():
		if src in string:
			string=tgt.join(string.split(src))
	return string

def split(string:str, splitter_symbols):
	base=[string]
	result=[]
	for symbol in splitter_symbols:
		for string in base:
			if not symbol in string:
				result.append(string)
			else:
				result+=string.split(symbol)
		base=result
		result=[]
	result = [ b.strip() for b in base if len(b.strip())>0 ]
	return result

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

	def add(self, input, splitter=""):
		""" input is either a file name, a string, a list of these or a stream """
		if isinstance(input,str):
			# string denotes a file
			if os.path.exists(input):
				with open(input,"rt",errors="ignore") as input:
					self.add(input,splitter=splitter)
					return
			# string may be a toolbox text => stream
			input=StringIO(input)

		if isinstance(input,list):
			# list => iterate
			for i in input:
				self.add(i,splitter=splitter)
			return

		# => processing an IGT stream
		alignments={self.target:self.source}

		# read, line-based
		raw=toolbox.read_toolbox_file(input)
		
		# aggregate according to document and record ids
		for (meta,record) in toolbox.records(raw,self.record_keys):
			try:
				warnings.simplefilter('ignore')
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
						# this is a unique target, however, alternative analyses may be possible, then marked by splitter symbols, and
						# we treat each one as an equally possible alternative
						for tgt in split(tgt,splitter):
							if not src in self.src2tgt2freq: self.src2tgt2freq[src]={}
							if not tgt in self.src2tgt2freq[src]: self.src2tgt2freq[src][tgt]=0
							self.src2tgt2freq[src][tgt]+=1
				sys.stderr.write(f"\rprocessed {meta}       \n")
			except toolbox.ToolboxAlignmentError as e:
				sys.stderr.write(f"\rskipping {meta}: {e}\n")
				sys.stderr.flush()
			warnings.resetwarnings()
			
	def sfst(self, output=None,freq_cutoff=0,ignore_case=True, skip_identicals=False, reduction_window=-1):
		""" spellout as SFST grammar

			use freq_cutoff to eliminate low-frequency mappings 
			if output is a stream or a file (name), write there,
			otherwise, return a string 

			with reduction window < 0, apply full-text matches, with 0, create rules for non-identical substrings, only, larger numbers entail a context window of preceding and following characters to be included in the match; values >= 0 entail -noident; defaults to -1",default=-1)
		"""

		if output==None:
			output=StringIO()
			self.sfst(freq_cutoff=freq_cutoff,output=output)
			return output.getvalue()

		if isinstance(output,str):
			with open(output,"wt") as output:
				return self.sfst(freq_cutoff=freq_cutoff,output=output)

		# output stream

		salph=set()
		talph=set()
		src2tgt2freq=self.src2tgt2freq
		if reduction_window>=0:
			# instead of full-word matches, store mismatching substrings, only; optionally, with predecing and following context (= -+ reduction_window)
			src2tgt2freq={}
			for src in self.src2tgt2freq:
				salph.update(src)
				for tgt,freq in self.src2tgt2freq[src].items():
					talph.update(tgt)

					if ignore_case:
						src=src.lower()
						tgt=tgt.lower()
					if src!=tgt:
						start=0
						while(start<len(src) and start<len(tgt) and src[start]==tgt[start]):
							start+=1
						end=-1
						while(-end <len(src) and -end <len(tgt) and src[end]==tgt[end]):
							end-=1
						
						src=src[max(0,start-reduction_window):min(len(src),len(src)+1+end+reduction_window)].strip()
						tgt=tgt[max(0,start-reduction_window):min(len(tgt),len(tgt)+1+end+reduction_window)].strip()
						if src!="" and tgt!="":
							if not src in src2tgt2freq: src2tgt2freq[src]={}
							if not tgt in src2tgt2freq[src]: src2tgt2freq[src][tgt]=0
							src2tgt2freq[src][tgt]+=freq

		name=re.sub(r"[^A-Z0-9_]","",(self.source+"_to_"+self.target).upper())
		name=f"${name}$"
		vals=[]
		for src in sorted(src2tgt2freq):
			salph.update(src)
			for tgt,freq in sorted(src2tgt2freq[src].items()):
				if freq>freq_cutoff:
					talph.update(tgt)

					# escape or filter here, if necessary
					src=escape(src,SFST_REPLACEMENTS)
					tgt=escape(tgt,SFST_REPLACEMENTS)
					if not "\\" in src: # no idea where this comes from
						if not skip_identicals or (not ignore_case and src!=tgt) or (ignore_case and src.lower()!=tgt.lower()):
							vals.append("{"+src+"}:{"+tgt+"} % freq "+str(freq))
		if len(vals)==0:
			raise Exception(f"empty grammar with frequency cutoff {freq_cutoff}")
		
		sys.stderr.write(f"=> {len(vals)} replacement rules\n")
		vals=" \\\n\t| ".join(vals)
		# this doesn't account for overlaps, in the source data, there are none, but there may be in the resulting data

		# if reduction_window<=0:
		# 	# no overlap => apply at once, i.e., plain disjunction
		# 	vals=" \\\n\t| ".join(vals)
		# else: 
		# 	# possible overlap => concatenate transducers
		# 	# unfortunately, this times out
		# 	vals="("+"\\\n\t | .)* || (".join(vals)+"\\\n\t| .)*"

		ident_rule=""
		if skip_identicals:
			ident_rule= "| .*"

		alph="".join(sorted(set(list(salph)+list(talph))))
		salph="".join(sorted(salph))
		talph="".join(sorted(talph))
		if "-" in salph: salph="".join(salph.split("-"))+"-"
		if "-" in talph: talph="".join(talph.split("-"))+"-"
		
		case_rule=""
		cased_chars=""
		for c in alph:
			if c.lower()!=c.upper():
				cased_chars+=c.lower()
		cased_chars="".join(sorted(set(cased_chars)))

		if ignore_case:
			case_rule="["+cased_chars.lower()+cased_chars.upper()+"]:["+cased_chars.upper()+cased_chars.lower()+"]"

		output.write(f"""
#SALPH#={escape(salph,SFST_REPLACEMENTS)}

#TALPH#={escape(talph,SFST_REPLACEMENTS)}

ALPHABET=[#SALPH#] [#TALPH#] {case_rule}

{name}={vals}

.+ || [#SALPH#]+ || {name} {ident_rule} || [#TALPH#]+\n""")

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
	args.add_argument("-s","--splitter_symbols",type=str,help="sometimes, Toolbox users cannot decide which analysis is correct and may put alternative analyses, separated by a special marker, e.g., ,, use this for splitting automatically, for the target marker, only")
	args.add_argument("-noident","--skip_identicals", action="store_true", help="if words on both ends are identical, don't create an extra rule, note that the resulting transducer will then be extended to spellout identical forms *in all cases*")
	args.add_argument("-r","--reduction_window",type=int, help="with -1, apply full-text matches, with 0, create rules for non-identical substrings, only, larger numbers entail a context window of preceding and following characters to be included in the match; values >= 0 entail -noident; defaults to -1",default=-1)
	args=args.parse_args()

	if args.reduction_window>=0:
		args.skip_identicals==True

	close_output=True
	if args.output==None:
		args.output=sys.stdout
		close_output=False
	else:
		args.output=open(args.output,"wt")

	if len(args.files)==0:
		sys.stderr.write(f"reading Toolbox data from stdin, note that we require markers {args.source} and {args.target} in the data\n")
		args.files.append(sys.stdin)
	else:
		i=0
		while(i<len(args.files)):
			file=args.files[i]
			if os.path.isdir(file):
				args.files+=[os.path.join(file,f) for f in os.listdir(file)]
				args.files=args.files[0:i]+args.files[i+1:]
			elif file.lower().endswith("txt") and not "backup of" in file.lower():
				i+=1
			else: # not a toolbox file
				args.files=args.files[0:i]+args.files[i+1:]

	me=FSTGenerator(args.source, args.target)
	me.add(args.files,splitter=args.splitter_symbols)
	# pprint(me.src2tgt2freq)

	me.sfst(args.output,freq_cutoff=args.freq_cutoff, ignore_case=args.ignore_case, skip_identicals=args.skip_identicals, reduction_window=args.reduction_window)
	args.output.flush()
	if close_output:
		args.output.close()