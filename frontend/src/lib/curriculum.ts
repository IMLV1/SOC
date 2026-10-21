export type TrainingStep = {
  id: string;
  title: string;
  target: string;
  explanation: string;
  limitation: string;
};

export type TrainingLesson = {
  id: string;
  level_id: string;
  version: number;
  title: string;
  steps: TrainingStep[];
};

export type TrainingLevel = {
  id: string;
  ordinal: number;
  title: string;
  objective: string;
  lessons: TrainingLesson[];
};

export type Curriculum = {
  schema_version: number;
  purpose: string;
  content_status: string;
  title: string;
  description: string;
  levels: TrainingLevel[];
};

// Only selects public authored content. This has no account progress or gate semantics.
export function selectTrainingStep(curriculum: Curriculum, lessonId: string | null, stepId: string | null) {
  const lessons = curriculum.levels.flatMap((level) => level.lessons);
  const lesson = lessons.find((item) => item.id === lessonId) ?? lessons[0];
  const level = curriculum.levels.find((item) => item.id === lesson.level_id)!;
  const stepIndex = Math.max(0, lesson.steps.findIndex((item) => item.id === stepId));
  return { level, lesson, step: lesson.steps[stepIndex], stepIndex, lessons };
}

export function trainingLink(lessonId: string, stepId?: string) {
  const search = new URLSearchParams({ lesson: lessonId });
  if (stepId) search.set("step", stepId);
  return `/demo/learning?${search}`;
}
