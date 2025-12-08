module lookup_table_a (
  input  [3:0] addr,
  output [7:0] data
);
  assign data = (addr == 4'h0) ? 8'h12 :
                (addr == 4'h1) ? 8'h34 :
                (addr == 4'h2) ? 8'h56 :
                (addr == 4'h3) ? 8'h78 :
                (addr == 4'h4) ? 8'h9A :
                (addr == 4'h5) ? 8'hBC :
                (addr == 4'h6) ? 8'hDE :
                (addr == 4'h7) ? 8'hF0 :
                8'h00;
endmodule

module lookup_table_b (
  input  [3:0] addr,
  output [7:0] data
);
  assign data = (addr == 4'h0) ? 8'hAB :
                (addr == 4'h1) ? 8'hCD :
                (addr == 4'h2) ? 8'hEF :
                (addr == 4'h3) ? 8'h01 :
                (addr == 4'h4) ? 8'h23 :
                (addr == 4'h5) ? 8'h45 :
                (addr == 4'h6) ? 8'h67 :
                (addr == 4'h7) ? 8'h89 :
                8'h00;
endmodule

module combinational_alu (
  input  [7:0] a,
  input  [7:0] b,
  input  [1:0] op,
  output [7:0] y
);
  wire [7:0] add_result;
  wire [7:0] sub_result;
  wire [7:0] and_result;
  wire [7:0] or_result;
  
  assign add_result = a + b;
  assign sub_result = a - b;
  assign and_result = a & b;
  assign or_result = a | b;
  
  assign y = (op == 2'b00) ? add_result :
             (op == 2'b01) ? sub_result :
             (op == 2'b10) ? and_result :
             (op == 2'b11) ? or_result :
             8'h00;
endmodule

module chip_top (
  input  clk,
  input  rst_n,
  output [7:0] gpio_a,
  output [7:0] gpio_b
);

  wire [7:0] rom_a_data;
  wire [7:0] rom_b_data;
  wire [7:0] alu_result;

  lookup_table_a u_rom_a (
    .addr(4'h0),
    .data(rom_a_data)
  );

  lookup_table_b u_rom_b (
    .addr(4'h1),
    .data(rom_b_data)
  );

  combinational_alu u_alu (
    .a(rom_a_data),
    .b(rom_b_data),
    .op(2'b00),
    .y(alu_result)
  );

  assign gpio_a = rom_a_data;
  assign gpio_b = alu_result;

endmodule