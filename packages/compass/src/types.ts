export type Axis = "economic" | "social";
export type LikertValue = -2 | -1 | 0 | 1 | 2;

export interface Question {
  id: string;
  text: string;
  axis: Axis;
  reverse: boolean;
  weight: number;
}

export interface Answer {
  questionId: string;
  value: LikertValue;
  timestamp: number;
}

export interface CompassResult {
  economic: number;
  social: number;
  quadrant: "libertarian_left" | "libertarian_right" | "authoritarian_left" | "authoritarian_right";
  confidence: number;
  consistency: number;
  partyMatches: PartyMatch[];
  completedAt: number;
}

export interface PartyMatch {
  name: string;
  nameEl: string;
  score: number;
  x: number;
  y: number;
  color: string;
}

export interface LiquidUpdate {
  billId: string;
  voteValue: "yes" | "no";
  compassAnswer?: Answer;
  timestamp: number;
}
