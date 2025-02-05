import { useEffect, useState } from 'react';
import dagre from 'dagre';
import ReactFlow, {
  NodeChange,
  applyNodeChanges,
  EdgeChange,
  applyEdgeChanges,
  Edge,
  Node,
  Position,
} from 'react-flow-renderer';
import { Box } from '@mui/material';

import { PanelFlowChart, PanelFlowChartData } from '@duct-core/data';

const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction = 'LR'
) => {
  // const nodeWidth = 150;
  // const nodeHeight = 40;
  // const dagreGraph = new dagre.graphlib.Graph();
  // const isHorizontal = direction === 'LR';
  // dagreGraph.setGraph({ rankdir: direction });
  // dagreGraph.setDefaultEdgeLabel(() => ({}));

  // nodes.forEach((node) => {
  //   dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  // });

  // edges.forEach((edge) => {
  //   dagreGraph.setEdge(edge.source, edge.target);
  // });

  // dagre.layout(dagreGraph);

  // nodes.forEach((node) => {
  //   const nodeWithPosition = dagreGraph.node(node.id);
  //   node.targetPosition = isHorizontal ? Position.Left : Position.Top;
  //   node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;

  //   // We are shifting the dagre node position (anchor=center center) to the top left
  //   // so it matches the React Flow node anchor point (top left).
  //   node.position = {
  //     x: nodeWithPosition.x - nodeWidth / 2,
  //     y: nodeWithPosition.y - nodeHeight / 2,
  //   };

  //   return node;
  // });

  return { nodes, edges };
};

interface FlowChartProps {
  data: PanelFlowChart;
}

function FlowChart(props: FlowChartProps) {
  const { data } = props;
  const [currentNodes, setCurrentNodes] = useState<Node[]>([]);
  const [currentEdges, setCurrentEdges] = useState<Edge[]>([]);

  const buildFlowChart = (
    chartData: PanelFlowChartData
  ): { edges: Edge[]; nodes: Node[] } => {
    const position = { x: 0, y: 0 };

    const nodes: Node[] = chartData.nodes.map((node) => {
      return {
        id: node.id,
        position,
        sourcePosition: Position.Left,
        targetPosition: Position.Right,
        data: { ...node.data },
        parentNode: node.parentNode ? node.parentNode : undefined,
        extent: node.parentNode ? 'parent' : undefined,
        style: {
          height: node.parentNode ? 90 : 350,
          width: node.parentNode ? 90 : 150,
          backgroundColor: node.parentNode ? undefined : 'transparent',
        },
      };
    });

    const edges: Edge[] = chartData.edges.map((edge) => {
      return { id: edge.id, target: edge.target, source: edge.source };
    });

    return { nodes, edges };
  };

  useEffect(() => {
    const chart = buildFlowChart(data.data);
    const formatted = getLayoutedElements(chart.nodes, chart.edges);
    setCurrentNodes(formatted.nodes);
    setCurrentEdges(formatted.edges);
  }, []);

  const onNodesChange = (nodes: NodeChange[]) =>
    setCurrentNodes((nds) => applyNodeChanges(nodes, nds));

  const onEdgesChange = (changes: EdgeChange[]) =>
    setCurrentEdges((eds) => applyEdgeChanges(changes, eds));

  return (
    <Box sx={{ height: 350, width: 370, border: '1px solid #ccc' }}>
      <ReactFlow
        nodes={currentNodes}
        edges={currentEdges}
        onEdgesChange={onEdgesChange}
        onNodesChange={onNodesChange}
        fitView
      ></ReactFlow>
    </Box>
  );
}

export default FlowChart;
