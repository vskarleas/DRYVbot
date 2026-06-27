<?php

namespace App\Services;

use Illuminate\Http\UploadedFile;
use Smalot\PdfParser\Parser;

class OcrService
{
    /**
     * Extract text from a PDF or image file.
     */
    public function extractText(UploadedFile $file): string
    {
        $mimeType = $file->getMimeType() ?? '';

        if (str_contains($mimeType, 'pdf')) {
            return $this->extractFromPdf($file->getPathname());
        }

        if (str_starts_with($mimeType, 'image/')) {
            return $this->extractFromImage($file->getPathname());
        }

        return '';
    }

    private function extractFromPdf(string $path): string
    {
        try {
            $parser = new Parser();
            $pdf = $parser->parseFile($path);
            return $pdf->getText();
        } catch (\Throwable) {
            return '';
        }
    }

    /**
     * Image OCR via Tesseract binary if available, otherwise returns empty string.
     */
    private function extractFromImage(string $path): string
    {
        if (! $this->tesseractAvailable()) {
            return '';
        }

        $output = shell_exec(sprintf(
            'tesseract %s stdout -l fra 2>/dev/null',
            escapeshellarg($path)
        ));

        return $output ?? '';
    }

    private function tesseractAvailable(): bool
    {
        return ! empty(shell_exec('which tesseract 2>/dev/null'));
    }

    /**
     * Try to parse an order reference and fields from raw OCR text.
     *
     * @return array<string, string>
     */
    public function parseOrderData(string $text): array
    {
        $data = [];

        if (preg_match('/salle\s+d[ée]part\s*:?\s*([A-Za-z0-9\-]+)/i', $text, $m)) {
            $data['departure_room'] = trim($m[1]);
        }

        if (preg_match('/salle\s+arriv[ée]e?\s*:?\s*([A-Za-z0-9\-]+)/i', $text, $m)) {
            $data['arrival_room'] = trim($m[1]);
        }

        if (preg_match('/contenu\s*:?\s*(.+)/i', $text, $m)) {
            $data['content'] = trim($m[1]);
        }

        return $data;
    }
}

