export function beginValidationRequest(sequence) {
  sequence.current += 1
  return sequence.current
}

export function isCurrentValidationRequest(sequence, requestId) {
  return sequence.current === requestId
}
