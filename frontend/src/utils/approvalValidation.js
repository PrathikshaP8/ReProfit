export const PRODUCT_MIN_CONFIDENCE = 60

export function normalizeProductValidation(validation) {
  return validation === 'MATCH' || validation === 'MISMATCH' ? validation : 'UNVERIFIED'
}

export function getVerifiedProductValidation(result, selectedExpectedProduct) {
  if (!result || typeof result !== 'object') return 'UNVERIFIED'

  const validation = normalizeProductValidation(result.product_validation)
  if (validation === 'UNVERIFIED') return validation

  const expected = typeof result.expected_product === 'string' ? result.expected_product.trim().toLowerCase() : ''
  const detected = typeof result.product_label === 'string' ? result.product_label.trim().toLowerCase() : ''
  const confidence = result.product_confidence
  if (
    !expected ||
    !detected ||
    typeof confidence !== 'number' ||
    !Number.isFinite(confidence) ||
    confidence < PRODUCT_MIN_CONFIDENCE ||
    confidence > 100 ||
    typeof result.product_matches !== 'boolean'
  ) {
    return 'UNVERIFIED'
  }

  if (
    typeof selectedExpectedProduct === 'string' &&
    selectedExpectedProduct.trim() &&
    expected !== selectedExpectedProduct.trim().toLowerCase()
  ) {
    return 'UNVERIFIED'
  }

  const categoriesMatch = detected === expected
  if (validation === 'MATCH' && result.product_matches && categoriesMatch) return 'MATCH'
  if (validation === 'MISMATCH' && !result.product_matches && !categoriesMatch) return 'MISMATCH'
  return 'UNVERIFIED'
}

export function getProductValidationMessage(validation) {
  const normalized = normalizeProductValidation(validation)
  if (normalized === 'MATCH') return 'Product image verified.'
  if (normalized === 'MISMATCH') return 'Product mismatch: upload an image of the selected return product.'
  return 'Product unverified: the image could not be reliably identified.'
}
