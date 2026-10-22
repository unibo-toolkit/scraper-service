from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Curriculum:
    """
    A study track of a course, for one academic year.

    The site lists a curriculum once per course, but a timetable exists per
    academic year, so one scraped curriculum becomes `duration_years` rows.
    The timetable fields are filled only when the curriculum is read back from
    the database.

    Attributes:
        code: Curriculum code, e.g. "B69-000". Unique inside a course and year.
        label: Human readable name shown on the site.
        academic_year: Year of study, 1-based. None for a freshly scraped
            curriculum, which is not bound to a year yet.
        id: Database id. None until the curriculum is stored.
        timetable_hash: Hash of the last scraped timetable. Equal to a fresh
            scrape means nothing has to be written.
        timetable_updated_at: When the timetable was last checked, not last
            changed: it is written even when the hash matched.
    """

    code: str
    label: str
    academic_year: Optional[int] = None
    id: Optional[UUID] = None
    timetable_hash: Optional[str] = None
    timetable_updated_at: Optional[datetime] = None

    @property
    def key(self) -> Tuple[str, Optional[int]]:
        """
        Natural key of the curriculum inside its course.

        Returns:
            (code, academic_year) pair, matching the curricula unique constraint.
        """
        return self.code, self.academic_year


@dataclass(frozen=True, slots=True)
class Course:
    """
    A degree program of the university.

    Attributes:
        unibo_id: Numeric id used by the UniBo site. The natural key.
        title_it: Italian title, always present.
        course_type: One of Bachelor, Master, SingleCycleMaster, matching the
            course_type enum of the database.
        title_en: English title. None for programs with no english page.
        campus: City the program is taught in.
        languages: Languages of instruction, as the site spells them.
        duration_years: Length of the program, which decides how many
            curriculum rows every code expands into.
        url: Course site url, the entry point every timetable scrape needs.
            None when the site url could not be resolved.
        area: Subject area of the program.
        curricula: Study tracks. Carry no academic_year when scraped, and one
            row per year when read from the database.
        id: Database id. None until the course is stored.
    """

    unibo_id: int
    title_it: str
    course_type: str
    title_en: Optional[str] = None
    campus: Optional[str] = None
    languages: Sequence[str] = field(default_factory=tuple)
    duration_years: Optional[int] = None
    url: Optional[str] = None
    area: Optional[str] = None
    curricula: Sequence[Curriculum] = field(default_factory=tuple)
    id: Optional[UUID] = None

    def title(self, lang: str) -> str:
        """
        Title in the requested language.

        Args:
            lang: Either "it" or "en".

        Returns:
            The english title when asked for and present, the italian one
            otherwise.
        """
        return (self.title_en if lang == "en" else self.title_it) or self.title_it

    def expand_curricula(self) -> List[Curriculum]:
        """
        Every curriculum code repeated for each academic year of the course.

        Deduplicated on purpose: the feed may list the same code twice, and all
        rows end up in a single INSERT ... ON CONFLICT DO UPDATE, which cannot
        touch the same row twice.

        Returns:
            One Curriculum per (code, academic_year).
        """
        expanded: Dict[Tuple[str, Optional[int]], Curriculum] = {}
        for year in range(1, (self.duration_years or 0) + 1):
            for curr in self.curricula:
                item = Curriculum(code=curr.code, label=curr.label, academic_year=year)
                expanded.setdefault(item.key, item)

        return list(expanded.values())


@dataclass(frozen=True, slots=True)
class CourseCurriculum:
    """
    A curriculum together with the course that owns it.

    The unit the timetable sync works on: it needs the course url to scrape and
    the curriculum hash to decide whether to write. Reading them as a pair keeps
    it to one query.

    Attributes:
        course: Owning course, without its curricula list filled.
        curriculum: The curriculum itself, with timetable_hash and
            timetable_updated_at populated.
    """

    course: Course
    curriculum: Curriculum
