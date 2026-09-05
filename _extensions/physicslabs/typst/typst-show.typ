// Quarto show partial — maps YAML metadata to the template function.
// `course` is the PDF header stamp, taken from `physicslabs.title`.
#show: doc => article(
  $if(title)$title: "$title$",$endif$
  $if(by-author)$authors: ($for(by-author)$(name: "$it.name.literal$"),$endfor$),$endif$
  $if(date)$date: "$date$",$endif$
  $if(physicslabs.title)$course: "$physicslabs.title$",$endif$
  $if(lang)$lang: "$lang$",$endif$
  $if(region)$region: "$region$",$endif$
  $if(abstract)$abstract: [$abstract$],$endif$
  $if(margin)$margin: ($for(margin/pairs)$$it.key$: $it.value$,$endfor$),$endif$
  $if(papersize)$paper: "$papersize$",$endif$
  $if(mainfont)$font: "$mainfont$",$endif$
  $if(fontsize)$fontsize: $fontsize$,$endif$
  $if(section-numbering)$sectionnumbering: "$section-numbering$",$endif$
  $if(toc)$toc: $toc$,$endif$
  $if(toc-title)$toc-title: "$toc-title$",$endif$
  $if(toc-depth)$toc-depth: $toc-depth$,$endif$
  $if(cols)$cols: $cols$,$endif$
  doc,
)
