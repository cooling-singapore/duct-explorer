import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
} from '@mui/material';
import { useEffect, useState } from 'react';

interface JsonTableProps {
  data: object;
}

function JsonTable(props: JsonTableProps) {
  const { data } = props;
  const [tableData, setTableData] = useState<JSX.Element[]>([]);
  const rightBorder = { borderRight: '1px solid #ccc' };

  const handleObject = (obj: object): JSX.Element[] => {
    const table: JSX.Element[] = [];
    for (const key of Object.keys(obj)) {
      const value = obj[key as keyof typeof obj];

      if (Array.isArray(value)) {
        const nestedRow: JSX.Element[] = [];
        (value as any[]).forEach((e) => {
          if (typeof e === 'object') {
            nestedRow.push(...handleObject(e));
          } else {
            nestedRow.push(<TableRow>{e}</TableRow>);
          }
        });

        table.push(
          <>
            <TableCell sx={rightBorder}>{key}</TableCell>
            <TableCell>{nestedRow}</TableCell>
          </>
        );
      } else if (typeof value === 'object') {
        table.push(
          <>
            <TableCell sx={rightBorder}>{key}</TableCell>
            {handleObject(value).map((cell) => (
              <TableRow>{cell}</TableRow>
            ))}
          </>
        );
      } else {
        table.push(
          <>
            <TableCell sx={rightBorder}>{key}</TableCell>
            <TableCell sx={rightBorder}>{value}</TableCell>
          </>
        );
      }
    }

    return table;
  };

  useEffect(() => {
    setTableData(handleObject(data));
  }, []);

  return (
    <TableContainer component={Paper} sx={{ minWidth: 800 }}>
      <Table size="small">
        <TableBody>
          {tableData.map((cell) => (
            <TableRow>{cell}</TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default JsonTable;
