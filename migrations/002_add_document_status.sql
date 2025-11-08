-- Add status column to pdf_document table
ALTER TABLE pdf_document 
ADD COLUMN IF NOT EXISTS status VARCHAR NOT NULL DEFAULT 'processing' 
CHECK (status IN ('processing', 'ready', 'failed'));

-- Create index on status for faster queries
CREATE INDEX IF NOT EXISTS idx_pdf_document_status ON pdf_document(status);

-- Update num_pages to allow 0 (default) since it's set during processing
ALTER TABLE pdf_document 
ALTER COLUMN num_pages SET DEFAULT 0;

