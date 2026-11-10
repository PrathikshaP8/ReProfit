import assert from 'node:assert/strict'
import test from 'node:test'
import { beginValidationRequest, isCurrentValidationRequest } from './validationRequestSequence.js'

test('only the latest image or item validation request can update the assessment', () => {
  const sequence = { current: 0 }
  const phoneImageRequest = beginValidationRequest(sequence)
  const switchedProductRequest = beginValidationRequest(sequence)
  const replacementMouseImageRequest = beginValidationRequest(sequence)

  assert.equal(isCurrentValidationRequest(sequence, phoneImageRequest), false)
  assert.equal(isCurrentValidationRequest(sequence, switchedProductRequest), false)
  assert.equal(isCurrentValidationRequest(sequence, replacementMouseImageRequest), true)
})
