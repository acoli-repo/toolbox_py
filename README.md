# toolbox

Python implementation of [SIL's Toolbox](www.sil.org/computing/toolbox)
Standard Format Markers (SFM) format. The basic format looks like this:

```
\mkr a line of text
```

Where `\mkr` is called a *marker* and is followed by a space, then one
or more lines of text.

The original code base is [https://github.com/goodmami/toolbox](https://github.com/goodmami/toolbox) by [Michael Wayne Goodman](https://github.com/goodmami) and [Elizabeth Conrad](https://github.com/lizcconrad). This fork is for an experimental extension with a routine to bootstrap SFST transducers from Toolbox data. This will use the Toolbox package, but as this is available via GitHub only, we're just creating a bundle ;)

## Basic Usage

The `toolbox` module is meant to be used as a library, not a script, so
you'll need to first make sure it's findable by Python. Either

1. copy `toolbox.py` to your project directory
2. install via pip (be careful to use the path and not just `toolbox` or
   it will install a different package from PyPI)

```bash
pip install ./toolbox/
```

You can then load it in Python and use it to read stored Toolbox files.
For example, the `read_toolbox_file()` function reads a Toolbox file and
yields (marker, text) pairs:

```python
>>> import toolbox
>>> for mkr, text in toolbox.read_toolbox_file(open('example/corpus.txt')):
...     print('Marker: {0!r:<8}Text: {1!r}'.format(mkr, text))
Marker: '\\ref' Text: 'item1'
Marker: '\\t'   Text: 'O        Pedro baixou'
Marker: '\\m'   Text: 'O        Pedro bai   -xou'
Marker: '\\g'   Text: 'the.M.SG Pedro lower -PST.IND.3SG'
Marker: '\\t'   Text: 'a        bola'
Marker: '\\m'   Text: 'a        bola'
Marker: '\\g'   Text: 'the.F.SG ball.F.SG'
Marker: '\\f'   Text: 'Pedro calmed down.'
Marker: '\\l'   Text: 'Pedro lowered the ball.'

```

(By default, trailing whitespace (including newlines) is stripped, but
this can be turned off.)

In this example corpus, we have a single record (starting with the
`\ref` marker), with text (`\t`), morphemes (`\m`), glosses (`\g`),
a free translation (`\f`), and a literal translation (`\l`).
Furthermore, the interlinear lines have been wrapped (perhaps from
Toolbox itself). Below I show how the `toolbox` module can handle these
kinds of examples.

## Extra Features

Beyond simply reading Toolbox files, the `toolbox` module can perform
some analysis of the data.

### Iterating over records based on keys

A Toolbox corpus file contains groups of (marker, text) pairs for
representing linguistic examples, called "records". Records are
delimited by certain markers (called, "record markers"), and there may
be more than one of such markers (e.g. `\ref` for each record, and
`\id` for grouping records into a text, etc.). The `records()` function
can automatically group the data in each record and keep track of the
context of the record markers previously seen. Here is how one might
read a corpus file with a `\id` key for a text (sub-corpus) and a `\ref`
key for each record.

```python
>>> pairs = toolbox.read_toolbox_file(open('example/corpus.txt'))
>>> for (context, data) in toolbox.records(pairs, ['\\id', '\\ref']):
...     print(sorted(context.items()))
...     print('\n'.join(map(repr, data)))
[('\\id', None), ('\\ref', 'item1')]
('\\t', 'O        Pedro baixou')
('\\m', 'O        Pedro bai   -xou')
('\\g', 'the.M.SG Pedro lower -PST.IND.3SG')
('\\t', 'a        bola')
('\\m', 'a        bola')
('\\g', 'the.F.SG ball.F.SG')
('\\f', 'Pedro calmed down.')
('\\l', 'Pedro lowered the ball.')

```

Note that there were no `\id` markers in the corpus file, so the value
is `None`.

### Normalizing tiers

Some toolbox data are line-wrapped, but logically the wrapped lines
continue where the first one stopped. Working with line-wrapped data
just makes things harder, so the `normalize_record()` function will
restore them to a single line per marker. As the function name implies,
this works on a record rather than file contents, so it may take the
results of the `records()` function. The second parameter to
`normalize_item()` is a container of markers for lines that should still
be visually aligned in columns after normalization.

```python
>>> pairs = toolbox.read_toolbox_file(open('example/corpus.txt'))
>>> records = toolbox.records(pairs, ['\\id', '\\ref'])
>>> rec1 = next(records)
>>> for mkr, val in toolbox.normalize_record(rec1[1], ['\\t', '\\g', '\\m']):
...     print((mkr, val))
('\\t', 'O        Pedro baixou             a        bola')
('\\m', 'O        Pedro bai   -xou         a        bola')
('\\g', 'the.M.SG Pedro lower -PST.IND.3SG the.F.SG ball.F.SG')
('\\f', 'Pedro calmed down.')
('\\l', 'Pedro lowered the ball.')

```

### Aligning fields

Toolbox encodes token alignments implicitly through spacing such that
aligned tokens appear visually in columns. The `toolbox` module provides
an `align_fields()` function to analyze the columns and return a more
explicit representation of the alignments. The function takes a list of
marker-text pairs and a marker-to-marker mapping to describe the
alignments. The result is a list of (marker, aligned_data) pairs, where
*aligned_data* is a list of (token, aligned_tokens).

```python
>>> pairs = toolbox.read_toolbox_file(open('example/corpus.txt'))
>>> records = toolbox.records(pairs, ['\\id', '\\ref'])
>>> rec1 = next(records)
>>> normdata = toolbox.normalize_record(rec1[1], ['\\t', '\\g', '\\m'])
>>> alignments = {'\\m': '\\t', '\\g': '\\m'}
>>> for mkr, algns in toolbox.align_fields(normdata, alignments=alignments):
...     print((mkr, algns))  # doctest: +NORMALIZE_WHITESPACE
('\\t', [('O        Pedro baixou             a        bola',
          ['O', 'Pedro', 'baixou', 'a', 'bola'])])
('\\m', [('O', ['O']),
         ('Pedro', ['Pedro']),
         ('baixou', ['bai', '-xou']),
         ('a', ['a']),
         ('bola', ['bola'])])
('\\g', [('O', ['the.M.SG']),
         ('Pedro', ['Pedro']),
         ('bai', ['lower']),
         ('-xou', ['-PST.IND.3SG']),
         ('a', ['the.F.SG']),
         ('bola', ['ball.F.SG'])])
('\\f', [(None, ['Pedro calmed down.'])])
('\\l', [(None, ['Pedro lowered the ball.'])])

```

## Extensions

### Bootstrapping FST grammars

Finite State Transducers (FST) are a very well-established formalism for rule-based transliteration, normalization and morphological annotation (and other fields). The package `tb2fst.py` uses the Toolbox package to bootstrap FST grammars from Toolbox dictionaries or glossed text.

There are various FST formalisms, at the moment, we support SFST, as this is readily available under various Linux distributions. The following is tested under Ubuntu 20.04L.

```bash
python3 tb2fst.py \tx \sf example/sliekkas_DK_1595.txt -f 0 -o sliekkas.fst -i
```

Run `python3 tb2fst.py -h` to get a more detailed explanation on the options. Here, we want to bootstrap a grammar that takes `\tx` input and produces `\sf` output (both referring to the original Toolbox markers). One or more Toolbox files or directories containing Toolbox files can be provided, here `example/sliekkas_DK_1595.txt`. For large data sets, `-f` can be used to specify a frequency threshold. `-o sliekkas.fst` specifies the resulting FST grammar. Finally, the flag `-i` indicates that the input (in generation mode) is processed in a case-insensitive manner.

If you have SFST installed (see [here](https://wiki.apertium.org/wiki/SFST)for instructions, but note that SFST is readily available for many distros, already, see [here](https://launchpad.net/ubuntu/trusty/+package/sfst) for Ubuntu), you can compile the resulting grammar:

```bash
fst-compiler-utf8 sliekkas.fst sliekkas.a
```

The result can be tested with `fst-mor`:

```bash
fst-mor sliekkas.a
```

Switch to generation mode by hitting `<ENTER>` and enter a word, e.g., `arba`. It should perform the lookup automatically.

Note that the resulting transducers are limited in their functionality to what Toolbox offers, as well. However, they can be combined with other FST grammars to handle aspects not covered by Toolbox-style dictionary lookup.

### FST grammars with generalization

Using the parameter `-r`/`--reduction_window` and value `0` for `tb2fst.py`, only mismatching substrings are included in the generated FST grammar. With integer values `> 0`, their context is included in the mapping rules, i.e., one preceding and one following character with `-r 1`.

```bash
python3 tb2fst.py \tx \sf example/sliekkas_DK_1595.txt -f 1 -o sliekkas_r1.fst -r 1
```

Note that frequencies are calculated for each occurrence of source and target before the cutoff is applied.

The resulting FST grammar will be much smaller, and more efficient, and also be able to process unseen words. But it will also generate more analyses, so manually curating the resulting FST grammar to filter out or refine rules is highly advisable. If `-r`-transductors become too large to be compiled effectively, increase the value of `-r`. This is also a good way to constrain over-generation.

## Examples and testing

The examples in this README file and in the [`tests.md`](tests.md) file
can be run as unit tests, while at the same time serving as useful
documentation. To run them as unit tests, do this from the command line:

```bash
python3 -m doctest README.md tests.md
```

## Acknowledgments

The development of the [original code base](https://github.com/goodmami/toolbox) by [Michael Wayne Goodman](https://github.com/goodmami) and [Elizabeth Conrad](https://github.com/lizcconrad) for parsing Toolbox files was partially supported by the Affectedness project, under
the Singapore Ministry of Education Tier 2 grant (grant number
MOE2013-T2-1-016). The extension for bootstrapping SFST transducers from Toolbox files is developed by [Christian Chiarcos](github.com/chiarcos) in the project [The Postil Time Machine: Innereuropäischer Wissenstransfer als Graph](https://gepris.dfg.de/gepris/projekt/443985248?language=en), funded by the German Research Foundation (DFG, 2021-2025, grant number 443985248).