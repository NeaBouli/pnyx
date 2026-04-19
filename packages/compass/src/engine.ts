/**
 * CompassEngine — deterministic Political Compass scoring.
 * Pure logic, no UI, no network, no storage.
 * Same inputs → same outputs. Always.
 */
import type { Question, Answer, CompassResult, PartyMatch } from "./types";
import { QUESTIONS } from "./questions";
import { PARTIES } from "./parties";

export class CompassEngine {
  private transformAnswer(q: Question, rawValue: number): number {
    const value = q.reverse ? rawValue * -1 : rawValue;
    return value * q.weight;
  }

  private computeAxisScore(axis: "economic" | "social", answers: Answer[]): number {
    const questions = QUESTIONS.filter(q => q.axis === axis);
    let weightedSum = 0;
    let totalWeight = 0;
    for (const q of questions) {
      const answer = answers.find(a => a.questionId === q.id);
      if (!answer) continue;
      weightedSum += this.transformAnswer(q, answer.value);
      totalWeight += q.weight;
    }
    return totalWeight > 0 ? weightedSum / totalWeight : 0;
  }

  private normalize(score: number): number {
    return Math.max(-10, Math.min(10, score * 3.5));
  }

  private computeConsistency(answers: Answer[]): number {
    const pairs: [string, string][] = [
      ["E1", "E2"], ["E4", "E7"], ["E6", "E10"], ["E8", "E12"],
      ["E11", "E19"], ["E14", "E17"], ["S1", "S4"], ["S2", "S9"],
      ["S5", "S6"], ["S8", "S11"], ["S10", "S13"], ["S17", "S20"],
    ];
    let contradictions = 0;
    let checked = 0;
    for (const [id1, id2] of pairs) {
      const a1 = answers.find(a => a.questionId === id1);
      const a2 = answers.find(a => a.questionId === id2);
      if (!a1 || !a2) continue;
      const q1 = QUESTIONS.find(q => q.id === id1)!;
      const q2 = QUESTIONS.find(q => q.id === id2)!;
      const n1 = q1.reverse ? -a1.value : a1.value;
      const n2 = q2.reverse ? -a2.value : a2.value;
      if (Math.sign(n1) === Math.sign(n2) && n1 !== 0) contradictions++;
      checked++;
    }
    return checked > 0 ? 1 - contradictions / checked : 1;
  }

  private computeConfidence(answers: Answer[], consistency: number): number {
    const values = answers.map(a => a.value);
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length;
    const varianceScore = Math.min(1, variance / 2);
    return consistency * 0.6 + varianceScore * 0.4;
  }

  private computePartyMatches(x: number, y: number): PartyMatch[] {
    const maxDist = Math.sqrt(20 * 20 + 20 * 20);
    return PARTIES.map(p => {
      const dist = Math.sqrt(Math.pow(x - p.x, 2) + Math.pow(y - p.y, 2));
      const score = Math.round(Math.max(0, 100 - (dist / maxDist) * 100));
      return { ...p, score };
    }).sort((a, b) => b.score - a.score);
  }

  compute(answers: Answer[]): CompassResult {
    const economic = this.normalize(this.computeAxisScore("economic", answers));
    const social = this.normalize(this.computeAxisScore("social", answers));
    const consistency = this.computeConsistency(answers);
    const confidence = this.computeConfidence(answers, consistency);
    const quadrant =
      economic < 0 && social < 0 ? "libertarian_left" as const :
      economic > 0 && social < 0 ? "libertarian_right" as const :
      economic < 0 && social > 0 ? "authoritarian_left" as const :
      "authoritarian_right" as const;
    return { economic, social, quadrant, confidence, consistency, partyMatches: this.computePartyMatches(economic, social), completedAt: Date.now() };
  }

  liquidUpdate(current: CompassResult, voteAxis: "economic" | "social" | null, voteDirection: number): CompassResult {
    if (!voteAxis) return current;
    const strength = 0.05;
    const economic = voteAxis === "economic" ? Math.max(-10, Math.min(10, current.economic + voteDirection * strength)) : current.economic;
    const social = voteAxis === "social" ? Math.max(-10, Math.min(10, current.social + voteDirection * strength)) : current.social;
    return { ...current, economic, social, partyMatches: this.computePartyMatches(economic, social) };
  }
}
