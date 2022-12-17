
#SALPH#=\=ABCEHIKLMNORSTW\|
#TALPH#=abcehiklmnorstv
ALPHABET=[#SALPH#] [#TALPH#] [=ABCEHIKLMNORSTVW|]:[=abcehiklmnorstvw|] [=abcehiklmnorstvw|]:[=ABCEHIKLMNORSTVW|]

$TX_TO_SF$={ARBA}:{arba} % freq 1 \
	| {KATHE\=\|\|CHISMAS}:{kathechismas} % freq 1 \
	| {KIEKWIENAM}:{kiekvienam} % freq 1 \
	| {MOKSLAS}:{mokslas} % freq 1

.+ || [#SALPH#]+ || $TX_TO_SF$ || [#TALPH#]+
