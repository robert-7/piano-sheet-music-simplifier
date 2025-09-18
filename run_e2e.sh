#!/bin/bash

# ==============================================================================
# End-to-End Music Processing Script
#
# This script automates the following workflow:
# 1. Converts a PDF score to a MusicXML file.
# 2. Performs harmony analysis on the generated MusicXML file.
# 3. Converts the MusicXML file back into a PDF.
#
# The script is designed to exit immediately if any command fails.
# ==============================================================================

# --- Configuration ---
# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
set -u
# Pipelines fail on the first command that fails, not the last.
set -o pipefail

# The input PDF file to process.
INPUT_PDF="user/input/Kakariko_Village.pdf"

# Extract the base name of the PDF file (e.g., "Kakariko_Village").
# This will be used to predict the output filenames.
BASENAME=$(basename "$INPUT_PDF" .pdf)

# --- Script Execution ---
echo "🚀 Starting end-to-end music processing for: $INPUT_PDF"

# 1. Define a unique output directory using the current timestamp.
# This keeps each run's output separate.
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
OUTPUT_DIR="user/output-${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"
LOG_FILE="${OUTPUT_DIR}/run_e2e.log"

echo "📂 Output will be saved in: ${OUTPUT_DIR}"
echo "📝 Logs will be written to: ${LOG_FILE}"
echo

# 2. Convert the source PDF to a MusicXML file.
echo "⏳ Step 1/3: Converting PDF to MusicXML..."
./main.py convert_pdf_to_musicxml --out-dir "${OUTPUT_DIR}" "${INPUT_PDF}" >> "${LOG_FILE}" 2>&1
echo "✅ PDF to MusicXML conversion complete."

# The expected path for the generated MusicXML file.
# Audiveris typically produces either .mxl or .musicxml files.
# Determine which MusicXML file was actually created.
echo "↪⏳ Validating MusicXML file was created..."
MUSICXML_OUTPUT_MXL="${OUTPUT_DIR}/${BASENAME}.mxl"
MUSICXML_OUTPUT_MUSICXML="${OUTPUT_DIR}/${BASENAME}.musicxml"
MUSICXML_OUTPUT_XML="${OUTPUT_DIR}/${BASENAME}.xml"
if [ -f "$MUSICXML_OUTPUT_MXL" ]; then
    MUSICXML_FILE="$MUSICXML_OUTPUT_MXL"
elif [ -f "$MUSICXML_OUTPUT_MUSICXML" ]; then
    MUSICXML_FILE="$MUSICXML_OUTPUT_MUSICXML"
elif [ -f "$MUSICXML_OUTPUT_XML" ]; then
    MUSICXML_FILE="$MUSICXML_OUTPUT_XML"
else
    echo "↪❌ Error: Could not find the generated MusicXML file." >&2
    echo "Looked for: $MUSICXML_OUTPUT_MXL" >&2
    echo "And: $MUSICXML_OUTPUT_MUSICXML" >&2
    echo "And: $MUSICXML_OUTPUT_XML" >&2
    exit 1
fi
echo "↪✅ Found MusicXML file: $MUSICXML_FILE"
echo

# 3. Analyze the harmony of the generated MusicXML file.
echo "⏳ Step 2/3: Analyzing harmony..."
./main.py generate_analysis_of_musicxml --out-dir "${OUTPUT_DIR}" "${MUSICXML_FILE}" >> "${LOG_FILE}" 2>&1
echo "✅ Harmony analysis complete."
echo "↪⏳ Validating analysis file was created..."
ANALYSIS_FILE="${OUTPUT_DIR}/${BASENAME}_analysis.json"
if [ -f "$ANALYSIS_FILE" ]; then
    echo "↪✅ Found analysis file: $ANALYSIS_FILE"
else
    echo "↪❌ Error: Could not find the generated analysis file." >&2
    echo "Looked for: $ANALYSIS_FILE" >&2
    exit 1
fi
echo

# 4. Convert the MusicXML file back to a PDF.
echo "⏳ Step 3/3: Converting MusicXML to PDF..."
# TODO: Consider adding --out-dir "${OUTPUT_DIR}" if supported by the command.
./main.py convert_musicxml_to_pdf "${MUSICXML_FILE}" >> "${LOG_FILE}" 2>&1
echo "✅ MusicXML to PDF conversion complete."
echo "↪⏳ Validating PDFs were created..."
PDF_OUTPUT_LILYPOND="${OUTPUT_DIR}/${BASENAME}.LilyPond.pdf.pdf"
if [ -f "$PDF_OUTPUT_LILYPOND" ]; then
    echo "↪✅ Found PDF file: $PDF_OUTPUT_LILYPOND"
else
    echo "↪❌ Error: Could not find the generated PDF file." >&2
    echo "Looked for: $PDF_OUTPUT_LILYPOND" >&2
    exit 1
fi
PDF_OUTPUT_MUSESCORE="${OUTPUT_DIR}/${BASENAME}.MuseScore.pdf"
if [ -f "$PDF_OUTPUT_MUSESCORE" ]; then
    echo "↪✅ Found PDF file: $PDF_OUTPUT_MUSESCORE"
else
    echo "↪❌ Error: Could not find the generated PDF file." >&2
    echo "Looked for: $PDF_OUTPUT_MUSESCORE" >&2
    exit 1
fi
echo

echo "🎉 End-to-end script finished successfully!"
