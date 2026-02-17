export function makeLocalParticipantId(): string {
  return `local_${crypto.randomUUID()}`;
}

export function isLocalParticipantId(participantId: string): boolean {
  return participantId.startsWith("local_");
}
