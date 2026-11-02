export const USER_ROLES = {
  ADMIN: 'admin',
  ENGINEER: 'engineer',
  SUPERVISOR: 'supervisor'
};

export const DOCUMENT_STATUSES = {
  UPLOADED: 'Uploaded',
  PROCESSING: 'Processing',
  INDEXED: 'Indexed',
  FAILED: 'Failed'
};

export const MANUAL_TYPES = [
  'Operations Manual',
  'Maintenance Manual',
  'Operations and Maintenance Manual',
  'Troubleshooting Guide',
  'Installation Manual',
  'Parts Catalog',
  'Safety Protocol'
];

export const ANSWER_STATUSES = {
  ANSWERED: 'answered',
  INSUFFICIENT_EVIDENCE: 'insufficient_evidence'
};

export const INSUFFICIENT_EVIDENCE_MESSAGE =
  "I couldn't find sufficient information in the selected machine's manuals to answer this question. Please check the available manuals or contact your supervisor.";
