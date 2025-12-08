module simple_rom #(
  parameter ADDRW = 4,
  parameter DATAW = 8
)(
  input  [ADDRW-1:0] addr,
  output reg [DATAW-1:0] data
);
  always @* begin
    case (addr[3:0])
      4'h0: data = 8'h12;
      4'h1: data = 8'h34;
      4'h2: data = 8'h56;
      4'h3: data = 8'h78;
      4'h4: data = 8'h9A;
      4'h5: data = 8'hBC;
      4'h6: data = 8'hDE;
      4'h7: data = 8'hF0;
      4'h8: data = 8'h0F;
      4'h9: data = 8'h1E;
      4'hA: data = 8'h2D;
      4'hB: data = 8'h3C;
      4'hC: data = 8'h4B;
      4'hD: data = 8'h5A;
      4'hE: data = 8'h6C;
      4'hF: data = 8'h7D;
      default: data = {DATAW{1'b0}};
    endcase
  end
endmodule

module simple_alu #(
  parameter W = 8
)(
  input  [W-1:0] a,
  input  [W-1:0] b,
  input  [1:0]   op,
  output reg [W-1:0] y
);
  always @* begin
    case (op)
      2'b00: y = a + b;
      2'b01: y = a - b;
      2'b10: y = a ^ b;
      2'b11: y = a & b;
      default: y = {W{1'b0}};
    endcase
  end
endmodule

module simple_accum #(
  parameter W = 8
)(
  input            clk,
  input            rst_n,
  input            en,
  input  [W-1:0]   d,
  output reg [W-1:0] q
);
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) q <= {W{1'b0}};
    else if (en) q <= d;
  end
endmodule

module chip_top (
  input         clk,
  input         rst_n,
  input  [7:0]  gpio_in,
  output [7:0]  gpio_out
);
  wire [3:0] rom_addr;
  wire [1:0] op;
  wire       acc_en;
  wire [7:0] rom_data;
  wire [7:0] acc_q;
  wire [7:0] alu_y;

  assign rom_addr = gpio_in[3:0];
  assign op       = gpio_in[5:4];
  assign acc_en   = gpio_in[7];

  simple_rom u_rom (
    .addr (rom_addr),
    .data (rom_data)
  );

  simple_accum u_acc (
    .clk  (clk),
    .rst_n(rst_n),
    .en   (acc_en),
    .d    (rom_data),
    .q    (acc_q)
  );

  simple_alu u_alu (
    .a  (acc_q),
    .b  (rom_data),
    .op (op),
    .y  (alu_y)
  );

  assign gpio_out = {alu_y[7:1], ^alu_y};
endmodule
