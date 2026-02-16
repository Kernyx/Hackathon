"use client";

import React, { useEffect, useRef } from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { toast } from 'sonner';

interface AgentNode {
  id: string;
  name: string;
  img?: HTMLImageElement;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
}



interface AgentLink {
  source: string | AgentNode;
  target: string | AgentNode;
  message?: string;
}

interface GraphData {
  nodes: AgentNode[];
  links: AgentLink[];
}

interface AgentGraphProps {
  data: GraphData;
  onNodeSelect?: (node: AgentNode) => void;
}

const AgentGraph: React.FC<AgentGraphProps> = ({ data, onNodeSelect }) => {
  const graphRef = useRef<ForceGraphMethods<AgentNode, AgentLink>>(undefined);
  useEffect(() => {
    if (graphRef.current) {
      setTimeout(() => {
        graphRef.current?.zoomToFit(400, 150); // 400мс анимация, 150px отступы
      }, 200);
    }
  }, [data]);
  useEffect(() => {
    data.nodes.forEach(node => {
    if (!node.img) {
        const img = new Image();
        img.src = `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(node.name)}`;
        img.onload = () => {
          node.img = img;
        };
    }
  });
  }, [data.nodes]);

  const drawNode = (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const size = 5;
    const { x, y, name, img } = node;

    ctx.beginPath();
    ctx.arc(x, y, size, 0, 2 * Math.PI, false);
    ctx.fillStyle = '#6366f1'; 
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5 / globalScale;
    ctx.stroke();

    if (img && img.complete) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, size - 0.5, 0, 2 * Math.PI, false);
    ctx.clip();
    ctx.drawImage(img, x - size, y - size, size * 2, size * 2);
    ctx.restore();
    }

    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.fillText(name, x, y + size + 2);
  };
const drawLinkCanvasObject = (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const MAX_FONT_SIZE = 4;

    const start = link.source;
    const end = link.target;

    if (typeof start !== 'object' || typeof end !== 'object') return;

    const relLink = { x: end.x - start.x, y: end.y - start.y };

    let textAngle = Math.atan2(relLink.y, relLink.x);
    if (textAngle > Math.PI / 2) textAngle = -(Math.PI - textAngle);
    if (textAngle < -Math.PI / 2) textAngle = -(-Math.PI - textAngle);

    const label = link.message || "";

    const fontSize = MAX_FONT_SIZE / globalScale;
    ctx.font = `${fontSize}px monospace`;
    
    ctx.save();
    ctx.translate(start.x + relLink.x / 2, start.y + relLink.y / 2);
    ctx.rotate(textAngle);

    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = 'rgba(99, 102, 241, 0.6)';
    ctx.fillText(label, 0, -2); 
    ctx.restore();
  };
  return (
    <div className="w-full h-250 rounded-xl overflow-hidden bg-transparent relative">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={drawNode}
        linkCanvasObject={drawLinkCanvasObject}
        linkCanvasObjectMode={() => 'after'}
        nodePointerAreaPaint={(node: any, color, ctx) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 14, 0, 2 * Math.PI, false);
          ctx.fill();
        }}
        onNodeClick={(node) => onNodeSelect?.(node as AgentNode)}

        linkColor={() => 'rgba(156, 163, 175, 0.3)'}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        linkDirectionalParticleWidth={2}
        onLinkClick={(link: any) => {
          const sourceName = typeof link.source === 'object' ? link.source.name : link.source;
          const targetName = typeof link.target === 'object' ? link.target.name : link.target;

          toast(`Установлен контакт: ${sourceName} -> ${targetName}`, {
          duration: 5000,
            position: 'bottom-right',
        });
        }}

        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
     />
    </div>
  );
};

export default AgentGraph;