from pathlib import Path

from physicslabs_build import naming


def test_page_stem_keeps_the_page_name():
    assert naming.page_stem(Path("index.qmd")) == "index.pdf"
    assert naming.page_stem(Path("labs/lab-01/index.qmd")) == "index.pdf"
    assert naming.page_stem(Path("getting-started/setup.qmd")) == "setup.pdf"


def test_prefixed_follows_the_phys4430_scheme():
    name = naming.prefixed("phys4430")
    # Every segment below the top-level category directory.
    assert name(Path("lab-guides/zeeman-effect/index.qmd")) == "phys4430-zeeman-effect.pdf"
    assert name(Path("lab-guides/gaussian-beams/week-1/index.qmd")) == "phys4430-gaussian-beams-week-1.pdf"
    # A category index falls back to the category itself.
    assert name(Path("lab-guides/index.qmd")) == "phys4430-lab-guides.pdf"
    # The site root.
    assert name(Path("index.qmd")) == "phys4430.pdf"
    # Pages that are not index.qmd keep their stem.
    assert name(Path("resources/lab-notebook/notes.qmd")) == "notes.pdf"
