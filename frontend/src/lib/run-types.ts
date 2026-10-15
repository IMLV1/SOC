// Domain DTO aliases from the approved contract; no independently maintained shapes.
export type { RunView as Run, EventView as Event, AlertView as Alert,
  AssessmentView as Assessment, TicketView as Ticket, NoteView as Note,
  TicketTimelineEntry, AnalysisView as Analysis } from "./api-types";
import type { RunView } from "./api-types";
export type RunStatus = RunView["status"];
