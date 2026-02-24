export const formatDate = (dateString: string | undefined): string => {
    if (!dateString) return '–';

    // Check if it's already in dd/mm/yyyy format (basic check)
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateString)) return dateString;

    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString; // Return original if invalid

    const isIso = /T/.test(dateString);
    const hasUtc = /Z$/.test(dateString) || /[+-]\d{2}:\d{2}$/.test(dateString);

    const day = (isIso || hasUtc ? date.getUTCDate() : date.getDate()).toString().padStart(2, '0');
    const month = ((isIso || hasUtc ? date.getUTCMonth() : date.getMonth()) + 1)
        .toString()
        .padStart(2, '0');
    const year = isIso || hasUtc ? date.getUTCFullYear() : date.getFullYear();

    return `${day}/${month}/${year}`;
};
