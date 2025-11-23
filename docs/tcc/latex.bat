rem perl.exe c:\texlive\2025\texmf-dist\scripts\latexmk\latexmk.pl -f -synctex=1 -interaction=nonstopmode -file-line-error -pdf -outdir=d:/Sandro/OneDrive/1_Estudos/CursoUSP/projetos/destra/docs/tcc d:/Sandro/OneDrive/1_Estudos/CursoUSP/projetos/destra/docs/tcc/tcc_sandro_fadiga
pdflatex tcc_apresentacao.tex
del *.aux
del *.loq
del *.gz
del *.bbl
del *.blg
del *.idx
del *.toc
del *.lot
del *.lof
del *.fls
del *.log
del *.ilg
del *.ind
del *.fdb_latexmk
del *.nav
del *.out
del *.snm

