
#SALPH#=\=ABCEHIKLMNORSTW\|

#TALPH#=abcehiklmnorstv

ALPHABET=[#SALPH#] [#TALPH#] [abcehiklmnorstvwABCEHIKLMNORSTVW]:[ABCEHIKLMNORSTVWabcehiklmnorstvw]

$TX_TO_SF$={ARBA}:{arba} % freq 1 \
	| {KIEKWIENAM}:{kiekvienam} % freq 1 \
	| {MOKSLAS}:{mokslas} % freq 1

.+ || [#SALPH#]+ || ($TX_TO_SF$ )  || [#TALPH#]+
