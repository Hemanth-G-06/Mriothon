// Mock data layer strictly separated for frontend development / fallback when Django backend is offline

export const MOCK_USERS = {
  admin: {
    id: 1,
    username: 'admin',
    first_name: 'Sarah',
    last_name: 'Connor',
    email: 'sarah.connor@gmail.com',
    full_name: 'Sarah Connor',
    role: 'admin',
    access: 'mock-access-token-admin',
    refresh: 'mock-refresh-token-admin'
  },
  engineer: {
    id: 2,
    username: 'engineer',
    first_name: 'Alex',
    last_name: 'Vance',
    email: 'alex.vance@gmail.com',
    full_name: 'Alex Vance',
    role: 'engineer',
    access: 'mock-access-token-engineer',
    refresh: 'mock-refresh-token-engineer'
  },
  supervisor: {
    id: 3,
    username: 'supervisor',
    first_name: 'Marcus',
    last_name: 'Brody',
    email: 'marcus.brody@gmail.com',
    full_name: 'Marcus Brody',
    role: 'supervisor',
    access: 'mock-access-token-supervisor',
    refresh: 'mock-refresh-token-supervisor'
  }
};

export const INITIAL_MOCK_MACHINES = [
  {
    id: 1,
    machine_code: 'M-HP200',
    name: 'HP-200 Hydraulic Forming Press',
    model_number: 'HP-200',
    serial_number: 'HP-2023-8891',
    description: 'Heavy industrial hydraulic forming press with dual prefill and proportional tonnage control.',
    location: 'Bay 3 - Press Shop',
    manuals_count: 2,
    created_at: '2025-01-15T09:30:00Z'
  },
  {
    id: 2,
    machine_code: 'M-AC90',
    name: 'AC-90 Air Compressor',
    model_number: 'AC-90',
    serial_number: 'AC-2022-4412',
    description: 'Variable-speed rotary screw air compressor providing clean dry pneumatic supply.',
    location: 'Compressor Room 1',
    manuals_count: 1,
    created_at: '2025-02-01T14:15:00Z'
  },
  {
    id: 3,
    machine_code: 'ABB-IRB-6700-01',
    name: 'ABB IRB 6700 Heavy Manipulator',
    model_number: 'IRB 6700-205/2.80',
    serial_number: 'ABB-2024-0078',
    description: 'Heavy industrial robotic manipulator for high-payload manufacturing tasks.',
    location: 'Bay 1, Assembly Line A',
    manuals_count: 1,
    created_at: '2025-03-10T11:00:00Z'
  }
];

export const INITIAL_MOCK_DOCUMENTS = [
  {
    id: 101,
    machine_id: 1,
    machine_code: 'M-HP200',
    machine_name: 'HP-200 Hydraulic Forming Press',
    title: 'HP 200 Operations Manual',
    manual_type: 'Operations Manual',
    model_number: 'HP-200',
    revision: 'Rev 1.0',
    file_name: 'HP200_Operations_Rev1_0.pdf',
    file_size: 91891,
    status: 'Ready',
    page_count: 3,
    created_at: '2025-01-16T10:00:00Z',
    pdf_url: '/sample-manual.pdf'
  },
  {
    id: 102,
    machine_id: 1,
    machine_code: 'M-HP200',
    machine_name: 'HP-200 Hydraulic Forming Press',
    title: 'HP 200 Maintenance Manual',
    manual_type: 'Maintenance Manual',
    model_number: 'HP-200',
    revision: 'Rev 1.0',
    file_name: 'HP200_Maintenance_Rev1_0.pdf',
    file_size: 91341,
    status: 'Ready',
    page_count: 3,
    created_at: '2025-01-18T16:20:00Z',
    pdf_url: '/sample-manual.pdf'
  },
  {
    id: 103,
    machine_id: 2,
    machine_code: 'M-AC90',
    machine_name: 'AC-90 Air Compressor',
    title: 'AC 90 Operations and Maintenance Manual',
    manual_type: 'Combined Operations and Maintenance Manual',
    model_number: 'AC-90',
    revision: 'Rev 1.0',
    file_name: 'AC90_Operations_Maintenance_Rev1_0.pdf',
    file_size: 98988,
    status: 'Ready',
    page_count: 3,
    created_at: '2025-02-05T11:45:00Z',
    pdf_url: '/sample-manual.pdf'
  }
];

export const INITIAL_MOCK_CHAT_HISTORY = [
  {
    id: 1,
    machine_id: 1,
    machine_name: 'HP-200 Hydraulic Forming Press',
    engineer_name: 'Alex Vance',
    engineer_id: 2,
    question: 'What is the required spindle warm-up procedure before operating at high RPM?',
    answer: 'Before exceeding 8,000 RPM, execute cycle `O9001` with spindle speed set at 3,000 RPM for 10 minutes, followed by 6,000 RPM for 5 minutes. Verify that the oil-air chiller indicates a reservoir temperature between 22°C and 25°C before initiating precision cutting.',
    is_insufficient_evidence: false,
    citations: [
      {
        id: 'cit-1',
        document_id: 101,
        document_title: 'HP-200 Operations Manual',
        revision: 'Rev 2.4',
        page_number: 34,
        snippet: 'Section 4.2 Spindle Warm-up Cycle: Cold starts without executing O9001 warmup may cause ceramic bearing micro-fractures.',
        pdf_url: '/sample-manual.pdf'
      },
      {
        id: 'cit-2',
        document_id: 102,
        document_title: 'HP-200 Maintenance Manual',
        revision: 'Rev 1.8',
        page_number: 89,
        snippet: 'Cooling lubrication reservoir operating range: 22°C - 25°C under continuous duty.',
        pdf_url: '/sample-manual.pdf'
      }
    ],
    created_at: '2025-04-10T10:14:00Z'
  },
  {
    id: 2,
    machine_id: 2,
    machine_name: 'AC-90 Industrial Chiller & Compressor',
    engineer_name: 'Alex Vance',
    engineer_id: 2,
    question: 'What pressure threshold activates the emergency shutoff valve on the compressor line?',
    answer: 'The primary safety pressure relief switch triggers an automatic hardware interlock cutoff when line pressure exceeds 14.5 bar (210 PSI). Additionally, if differential oil pressure drops below 1.2 bar for more than 15 consecutive seconds, error code `E-302` shuts down the compressor.',
    is_insufficient_evidence: false,
    citations: [
      {
        id: 'cit-3',
        document_id: 103,
        document_title: 'AC-90 Operations and Maintenance Manual',
        revision: 'Rev 3.1',
        page_number: 48,
        snippet: 'Automatic Interlock Shutoff: Dual-stage pressure sensor calibrated for 14.5 bar hard-trip limit.',
        pdf_url: '/sample-manual.pdf'
      }
    ],
    created_at: '2025-04-11T13:40:00Z'
  },
  {
    id: 3,
    machine_id: 1,
    machine_name: 'HP-200 Hydraulic Forming Press',
    engineer_name: 'Alex Vance',
    engineer_id: 2,
    question: 'Can I replace the hydraulic fluid with synthetic bio-diesel blend 5W-30?',
    answer: "I couldn't find sufficient information in the selected machine's manuals to answer this question.",
    is_insufficient_evidence: true,
    citations: [],
    created_at: '2025-04-12T09:05:00Z'
  }
];
