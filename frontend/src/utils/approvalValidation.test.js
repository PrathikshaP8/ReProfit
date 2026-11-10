import assert from 'node:assert/strict'
import test from 'node:test'
import {
  getProductValidationMessage,
  getVerifiedProductValidation,
  normalizeProductValidation,
} from './approvalValidation.js'

function prediction(validation, expected, detected, confidence = 90) {
  return {
    product_validation: validation,
    product_matches: validation === 'MATCH',
    expected_product: expected,
    product_label: detected,
    product_confidence: confidence,
  }
}

test('matching product category is accepted without claiming exact model verification', () => {
  const result = prediction('MATCH', 'Mobile Phone', 'Mobile Phone')
  assert.equal(getVerifiedProductValidation(result, 'Mobile Phone'), 'MATCH')
  assert.equal(
    getProductValidationMessage('MATCH'),
    'Product category matches the image; exact model is not verified.',
  )
})

test('phone returns reject mouse and sandals, and laptops reject mouse', () => {
  assert.equal(
    getVerifiedProductValidation(prediction('MISMATCH', 'Mobile Phone', 'Mouse', 89), 'Mobile Phone'),
    'MISMATCH',
  )
  assert.equal(
    getVerifiedProductValidation(prediction('MISMATCH', 'Mobile Phone', 'Sandals', 86), 'Mobile Phone'),
    'MISMATCH',
  )
  assert.equal(
    getVerifiedProductValidation(prediction('MISMATCH', 'Laptop', 'Mouse', 92), 'Laptop'),
    'MISMATCH',
  )
  assert.equal(getProductValidationMessage('MISMATCH'), 'Product and image mismatch')
})

test('old results, low confidence, and malformed payloads cannot verify a new image', () => {
  const oldPhoneMatch = prediction('MATCH', 'Mobile Phone', 'Mobile Phone')
  const newMouseMismatch = prediction('MISMATCH', 'Mobile Phone', 'Mouse')
  assert.equal(getVerifiedProductValidation(oldPhoneMatch, 'Laptop'), 'UNVERIFIED')
  assert.equal(getVerifiedProductValidation(newMouseMismatch, 'Mobile Phone'), 'MISMATCH')
  assert.equal(
    getVerifiedProductValidation(prediction('MATCH', 'Mobile Phone', 'Mobile Phone', 59.9), 'Mobile Phone'),
    'UNVERIFIED',
  )
  assert.equal(
    getVerifiedProductValidation({ product_validation: 'MATCH', product_matches: true }, 'Mobile Phone'),
    'UNVERIFIED',
  )
})

test('unknown and unrecognized results remain blocked and display the unverified result', () => {
  assert.equal(normalizeProductValidation(null), 'UNVERIFIED')
  assert.equal(getProductValidationMessage(null), 'Unable to verify product image.')
  assert.equal(getProductValidationMessage('unknown'), 'Unable to verify product image.')
})
